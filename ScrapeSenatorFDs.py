# A script to track recent stock trades by Congress members
import csv
import time
import sqlite3
from sqlite3 import Error

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains


# Scrape the report data from the senate EFD website & store in CSV
def scrape_headers(driver, connection):
    # Open the web page
    url = 'https://efdsearch.senate.gov/search/'
    driver.get(url)

    # Search for the periodic transaction reports of active senators
    driver.find_element_by_id('agree_statement').click()    # Agree not to use the data for anything illegal
    driver.find_element_by_class_name('form-check-input.senator_filer').click()     # Check the senator checkbox
    driver.find_element_by_class_name('btn.btn-primary').click()    # Click search
    driver.find_element_by_class_name('form-control.ml-1.mr-1').send_keys('100')    # Show 100 results
    time.sleep(1)   # Wait a second
    driver.find_element_by_class_name('form-control.table__search.ml-2').send_keys('Periodic Transaction Report')   # Search for PTRs
    time.sleep(1)   # Wait a second
    driver.find_element_by_xpath('//*[contains(@aria-label,\'Date\')]').click()     # Sort by ascending date
    time.sleep(1)   # Wait a second

    # Initialize empty lists to store data
    report_headers, report_links, report_transactions = ([] for i in range(3))

    # Loop through each page
    while True:
        # Pull header info & report links - relies on table being 5 columns in the correct order
        report_headers.extend([cell.text for cell in driver.find_elements_by_xpath('.//td')])
        report_links.extend([link.get_attribute('href') for link in driver.find_elements_by_xpath('//a[contains(@href,\'search/view\')]')])

        # If the page just scraped was the last page, the scraping process is done
        if driver.find_elements_by_class_name('paginate_button')[-2].get_attribute('class') == 'paginate_button current':
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

    # Remove PDF reports
    header = header[~header.report_link.str.contains('paper')].reset_index(drop=True)

    # Remove reports that have more recent amendments
    header = ignore_amended(header).reset_index(drop=True)

    # Export data
    header.to_sql(name='header', con=connection, if_exists='replace', index_label='report_id')
    header.to_csv('header.csv')


# Scrape transactions  -- not revised to use database yet
def scrape_transactions(browser, connect):
    # Open the web page & agree not to use the data for anything illegal
    url = 'https://efdsearch.senate.gov/search/'
    browser.get(url)
    browser.find_element_by_id('agree_statement').click()

    # Pull the header table
    hdr = pd.read_sql_query('SELECT * FROM header', con=connect, index_col='report_id')

    all_transactions = []

    # Store the transactions of each report
    for index, link in hdr.iterrows():
        print('link = ', link['report_link'])
        # Open report in new tab & switch to it
        browser.get(link['report_link'])
        time.sleep(2)

        # Store all transactions as a single list
        report_transactions = list(split_list(list(cell.text for cell in browser.find_elements_by_xpath('.//td')), 9))

        # Add relevant report id for linking to header table
        for trn in report_transactions:
            trn.insert(0, index)
            all_transactions.append(trn)

    # Data frame for transactions
    transactions = pd.DataFrame(all_transactions, columns=['report_id', 'transaction_id', 'transaction_date', 'owner', 'security',
                                                           'company', 'security_type', 'transaction_type', 'amount_range', 'comment'])

    # Export data
    transactions.to_sql(name='transactions', con=connect, if_exists='replace', index_label='mstr_trn_id')
    transactions.to_csv('transactions.csv')


# Give an overview of the database
def view_database(con):
    all_data = pd.read_sql_query('SELECT * FROM header, transactions WHERE header.report_id = transactions.report_id', con=con, index_col='mstr_trn_id')
    print(all_data)
    all_data.to_csv('SenateEFDs.csv')


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


# Split a long list 'list' into smaller lists of length 'n'
def split_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# Chrome driver path
driver_path = 'C:\\bin\\chromedriver.exe'
# Database path
db_path = 'C:\\Users\\RyanDodds\\Documents\\GitHub\\Senator_Stock_Trading\\SenateEFDs.db'

# Turn function calls on / off
scrp_headers = False
scrp_transactions = False
view = True

# Scrape new reports / transactions
if scrp_headers:
    hd_driver = webdriver.Chrome(executable_path=driver_path)
    hd_conn = sqlite3.connect(db_path)
    scrape_headers(hd_driver, hd_conn)

# Scrape new transactions
if scrp_transactions:
    trn_driver = webdriver.Chrome(executable_path=driver_path)
    trn_conn = sqlite3.connect(db_path)
    scrape_transactions(trn_driver, trn_conn)

# Let's actually use that data we worked so hard to get
if view:
    view_conn = sqlite3.connect(db_path)
    view_database(view_conn)
