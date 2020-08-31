# A script to track recent stock trades by Congress members
import csv
import time
import sqlite3

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# Create database schema only if it doesn't already exist
def create_db_tables(c):
    create_header_table = """ CREATE TABLE IF NOT EXISTS header (
                                         report_id integer PRIMARY KEY,
                                         first_name text,
                                         last_name text,
                                         report_title text,
                                         date_filed text,
                                         report_link text); """
    c.execute(create_header_table)
    create_transactions_table = """CREATE TABLE IF NOT EXISTS transactions (
                                     master_transaction_id integer PRIMARY KEY,
                                     report_id integer NOT NULL,
                                     transaction_id integer NOT NULL,
                                     transaction_date text,
                                     owner text,
                                     security text,
                                     company text,
                                     security_type text,
                                     transaction_type text,
                                     amount_range text,
                                     comment text,
                                     FOREIGN KEY (report_id) REFERENCES header (report_id));"""
    c.execute(create_transactions_table)


# Determine most recent report date. Clear out data from that day to ensure the delta load gets everything
def most_recent_report(sql_db, crsr):
    # Reports up to what date have already been scraped
    file_dates = pd.read_sql_query('SELECT DISTINCT date_filed FROM header', con=sql_db)
    file_dates['date_filed'] = file_dates['date_filed'].astype('datetime64[ns]')
    max_date = max(file_dates['date_filed'])

    # Remove report headers filed on the most recent file date
    del_rep_query = """DELETE FROM header
                        WHERE (report_id NOT IN (SELECT DISTINCT report_id FROM transactions))
                        OR date_filed=?"""
    crsr.execute(del_rep_query, (str(max_date),))

    # Remove report transactions associated with reports that were removed
    trn_wo_rep_query = """DELETE FROM transactions
                            WHERE report_id NOT IN (SELECT DISTINCT report_id FROM header)"""
    crsr.execute(trn_wo_rep_query)

    # Commit the database updates
    sql_db.commit()
    return str(max_date)


# Open a Selenium browser while printing status updates. Return said browser for use in scraping.
def open_efd_website():
    # Selenium browser options
    chrome_options = Options()
    chrome_options.add_argument("--headless")       # Comment out to watch browser while scraping

    # Open the browser
    print('Opening Selenium browser')
    chromedriver_path = 'C:\\Users\\RyanDodds\\Documents\\chromedriver_win32\\chromedriver.exe'
    sele = webdriver.Chrome(executable_path=chromedriver_path, options=chrome_options)
    print('Selenium browser opened')

    # Open Senate EFD website
    print('Opening senate EFD website')
    sele.get('https://efdsearch.senate.gov/search/')
    print('Senate EFD website opened')

    # Agree not to use the data for anything illegal
    print('Agreeing to not use the data for anything illegal')
    sele.find_element_by_id('agree_statement').click()
    print('Terms & Conditions have been accepted')
    return sele


# Scrape the report data from the senate EFD website. Stored in database table called 'header'.
def scrape_headers(driver, connection, from_date):
    # Search for the periodic transaction reports of active senators
    driver.find_element_by_class_name('form-check-input.senator_filer').click()  # Check the senator checkbox
    time.sleep(1)  # Wait a second
    driver.find_element_by_id('fromDate').send_keys(from_date)
    time.sleep(1)  # Wait a second
    driver.find_element_by_class_name('btn.btn-primary').click()  # Click search
    time.sleep(1)  # Wait a second
    driver.find_element_by_class_name('form-control.ml-1.mr-1').send_keys('100')  # Show 100 results
    time.sleep(1)  # Wait a second
    driver.find_element_by_class_name('form-control.table__search.ml-2').send_keys(
        'Periodic Transaction Report')  # Search for PTRs
    time.sleep(1)  # Wait a second
    driver.find_element_by_xpath('//*[contains(@aria-label,\'Date\')]').click()  # Sort by ascending date
    time.sleep(1)  # Wait a second

    # Initialize empty lists to store data
    report_headers, report_links = ([] for i in range(2))

    # Loop through each page
    while True:
        # Pull header info & report links - relies on table being 5 columns in the correct order
        report_headers.extend([cell.text for cell in driver.find_elements_by_xpath('.//td')])
        report_links.extend([link.get_attribute('href')
                             for link in driver.find_elements_by_xpath('//a[contains(@href,\'search/view\')]')])

        # If the page just scraped was the last page, the scraping process is done
        if driver.find_elements_by_class_name('paginate_button')[-2].get_attribute(
                'class') == 'paginate_button current':
            # Close the driver
            driver.quit()
            break
        # If we aren't done, go to the next page and let it load
        else:
            driver.find_element_by_class_name('paginate_button.next').click()
            time.sleep(2)

    # Split header data into 'parallel' lists
    first_name, last_name, report_title, date_filed = ([] for i in range(4))
    first_name.extend(report_headers[0::5])
    last_name.extend(report_headers[1::5])
    report_title.extend(report_headers[3::5])
    date_filed.extend(report_headers[4::5])

    # Create header data frame
    header_list = list(zip(first_name, last_name, report_title, date_filed, report_links))
    header = pd.DataFrame(header_list, columns=['first_name', 'last_name', 'report_title', 'date_filed', 'report_link'])
    header['date_filed'] = header['date_filed'].astype('datetime64[ns]')

    # Remove PDF reports
    header = header[~header.report_link.str.contains('paper')].reset_index(drop=True)

    # Remove reports that have more recent amendments
    header = ignore_amended(header).reset_index(drop=True)

    # Export data
    header.to_sql(name='header', con=connection, if_exists='append', index=False)

    return


# Scrape transactions within each report. Stored in database table called 'transactions'.
def scrape_transactions(browser, connect, cursor):
    # Pull the report links that need to be scraped
    links_query = """SELECT report_id, report_link
                     FROM header
                     WHERE report_id NOT IN (SELECT DISTINCT report_id FROM transactions)"""
    links = cursor.execute(links_query).fetchall()

    # Print number of reports to scrape
    num_links = str(len(links))
    print(num_links + ' report(s) to scrape')

    all_transactions = []

    # Store the transactions of each report
    for report_info in links:
        # Log status
        current_link = str(links.index(report_info) + 1)
        print('Scraping report ' + current_link + ' of ' + num_links)

        # Split tuple into two variables
        rep_num = report_info[0]
        link = report_info[1]

        # Open report in new tab & switch to it
        browser.get(link)
        time.sleep(2)

        # Store all transactions as a single list
        report_transactions = list(split_list(list(cell.text for cell in browser.find_elements_by_xpath('.//td')), 9))

        # Add relevant report id for linking to header table
        for trn in report_transactions:
            trn.insert(0, rep_num)
            all_transactions.append(trn)

    # Data frame for transactions
    transactions = pd.DataFrame(all_transactions, columns=['report_id', 'transaction_id', 'transaction_date',
                                                           'owner', 'security', 'company', 'security_type',
                                                           'transaction_type', 'amount_range', 'comment'])

    # Export data
    transactions.to_sql(name='transactions', con=connect, if_exists='append', index=False)


# Ignore reports that have been amended. Based on report title. Avoids unnecessary transaction scraping.
def ignore_amended(df):
    # Store list of report titles that contain 'Amendment'
    amendments = df[df['report_title'].str.contains('Amendment')].drop(columns=['date_filed'])
    ignore = []

    # Loop through the list of amended reports
    for ind, amd in amendments.iterrows():
        # Store the root title of the report
        title = amd.report_title[0:len('Periodic Transaction Report for 00/00/0000')]

        # Store the version (number after amendment)
        try:
            version = int(amd.report_title[-2:-1])
        except:
            version = 1  # If a version is not listed, assume it is the first and only amendment

        # Store the information for the reports which should be ignored
        for v in range(version):
            if v:
                ignore.append([amd.first_name, amd.last_name, title + ' (Amendment ' + str(v) + ')'])
            else:
                ignore.append([amd.first_name, amd.last_name, title])

    # Log ignore lists
    with open('amended_reports.csv', 'w', newline='') as fl:
        writer = csv.writer(fl)
        writer.writerows(ignore)

    # Remove rows matching the ignore list
    for row in range(len(df)):
        unique = [df['first_name'][row], df['last_name'][row], df['report_title'][row]]
        if unique in ignore:
            df = df.drop([row])

    # Return the data frame
    return df


# Dump the database to CSVs
def database_to_csv(database):
    # Open cursor
    cursor = database.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    # Store each table in a CSV
    for table_name in tables:
        table_name = table_name[0]
        table = pd.read_sql_query("SELECT * from %s" % table_name, database)
        table.to_csv(table_name + '.csv', index=False)

    # Combine header & transaction data in CSV
    reports = pd.read_sql_query('SELECT * FROM header, transactions WHERE header.report_id = transactions.report_id',
                                con=database)
    reports.to_csv('SenateEFDs.csv')

    # Close the cursor
    cursor.close()


# Split a long list 'list' into smaller lists of length 'n'
def split_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# Main function
def main():
    # Open SQLite database connection
    db_path = 'C:\\Users\\RyanDodds\\Documents\\GitHub\\Senator_Stock_Trading\\SenateEFDs.db'
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    # Create database tables if necessary
    create_db_tables(cur)

    # Clear any data filed on the most recent file date
    try:
        start_datetime = most_recent_report(db, cur)
        start_date = start_datetime[5:7] + '/' + start_datetime[8:10] + '/' + start_datetime[:4]
    except:
        start_date = '01/01/2012'
        print('No max date found')
    print('Scraping reports filed on or after ' + start_date)

    # Scrape header information from new reports
    print('Scraping report header information')
    scrape_headers(open_efd_website(), db, start_date)
    print('Done scraping report header information')

    # Scrape transactions from new reports
    print('Scraping transaction information')
    scrape_transactions(open_efd_website(), db, cur)
    print('Done scraping transaction information')

    # Dump database tables to CSVs
    print('Dumping database to CSVs')
    database_to_csv(db)
    print('Done dumping database to CSVs')


# Let's get it going
if __name__ == "__main__":
    main()