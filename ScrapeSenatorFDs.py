# A script to track recent stock trades by Congress members
import csv
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains


def scrape_senate_efds():
    # Open the webpage
    url = 'https://efdsearch.senate.gov/search/'
    DRIVER_PATH = 'C:\\bin\chromedriver.exe'
    driver = webdriver.Chrome(executable_path=DRIVER_PATH)
    driver.get(url)
    # Agree not to use the data for anything illegal
    agree_checkbox = driver.find_element_by_id('agree_statement')
    agree_checkbox.click()
    # Limit the selections to active senators, then click search. The Periodic Transactions checkbox would filter out amendments and cannot be used.
    senator_checkbox = driver.find_element_by_class_name('form-check-input.senator_filer')
    senator_checkbox.click()
    search_button = driver.find_element_by_class_name('btn.btn-primary')
    search_button.click()

    # Show 100 results, search for Periodic Transaction Reports, and sort descending by date filed
    results_dropdown = driver.find_element_by_class_name('form-control.ml-1.mr-1')
    results_dropdown.send_keys('100')
    time.sleep(1)
    filter_search = driver.find_element_by_class_name('form-control.table__search.ml-2')
    filter_search.send_keys('Periodic Transaction Report')
    time.sleep(1)
    date_header = driver.find_element_by_xpath('//*[contains(@aria-label,\'Date\')]')
    date_header.click()
    time.sleep(1)
    date_header.click()
    time.sleep(1)

    # # TO BE ADDED - some sort of way to only scrape new reports instead of doing a full read each time
    # if path.exists('header.csv') and path.exists('transactions.csv'):
    #     report_headers = pd.read_csv('header.csv')
    #     report_transactions = [list(row) for row in pd.read_csv('transactions.csv').values]
    # else:

    # If there are no existing files, initialize empty lists to store data
    report_headers, report_transactions = ([] for i in range(2))

    # Loop through each page
    while True:
        # Pull header info from rows of table - relies on table being 5 columns in the correct order
        report_headers.extend([cell.text for cell in driver.find_elements_by_xpath('.//td')])

        # Store list of links to be opened
        report_links = driver.find_elements_by_xpath('//a[contains(@href,\'search/view\')]')

        # Ensure the first report is within view
        actions = ActionChains(driver)
        actions.move_to_element(report_links[0]).perform()

        # Store the transactions of each report
        for link in report_links:
            # Open report in new tab & switch to it
            link.click()
            driver.switch_to.window(driver.window_handles[1])

            # Store all transactions as a single list - relies on table being
            report_transactions.append(
                [cell.text.replace('\n', ' ') for cell in driver.find_elements_by_xpath('.//td')])

            # Close the report tab & switch back to search results
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

        # If the page just scraped was the last page, the scraping process is done
        if driver.find_elements_by_class_name('paginate_button')[-2].get_attribute('class') == 'paginate_button current':
            # Close the driver
            driver.quit()
            break
        # If we aren't done, go to the next page and let it load
        else:
            driver.find_element_by_class_name('paginate_button.next').click()
            time.sleep(2)

        # Split header data into 4 'parallel' lists
        first_name, last_name, report_title, date_filed, senate_trades = ([] for i in range(5))
        first_name.extend(report_headers[0::5])
        last_name.extend(report_headers[1::5])
        report_title.extend(report_headers[3::5])
        date_filed.extend(report_headers[4::5])

        # Create header data frame
        header_list = list(zip(first_name, last_name, report_title, date_filed))
        header_df = pd.DataFrame(header_list, columns=['first_name', 'last_name', 'report_title', 'date_filed'])

        # Export data to CSVs for logging
        header_df.to_csv('header.csv')
        with open('transactions.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(report_transactions)


# Combine header data & transaction data
def merge_data():
    # Read header CSV file into a data frame
    header = pd.read_csv('header.csv', index_col=0)

    # Read transactions CSV file as a list of lists
    with open('transactions.csv', 'r') as read_obj:
        csv_reader = csv.reader(read_obj)
        transactions = list(csv_reader)

    # Determine which reports have been amended later and should be ignored
    amendments = header[header['report_title'].str.contains('Amendment')].drop(columns=['date_filed'])
    ignore = []
    for ind, amd in amendments.iterrows():
        # Store the title of the report without any amendments
        title = amd.report_title[0:len('Periodic Transaction Report for 00/00/0000')]

        # Store the version (number after amendment)
        try:
            version = int(amd.report_title[-2:-1])
        except:
            version = 1  # If a version if not listed, assume it is the first and only amendment

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

    # Create master data set by looping through each set of transactions
    senate_trades = []
    for rep in range(len(transactions)):
        # Skip reports on the ignore list
        if not [header['first_name'][rep], header['last_name'][rep], header['report_title'][rep]] in ignore:
            # For each existing transaction, save the header & transaction information
            for trns in range(int(len(transactions[rep]) / 9)):
                senate_trades.append([header['first_name'][rep], header['last_name'][rep], header['report_title'][rep],
                                      header['date_filed'][rep], transactions[rep][9 * trns],
                                      transactions[rep][9 * trns + 1], transactions[rep][9 * trns + 3],
                                      transactions[rep][9 * trns + 4], transactions[rep][9 * trns + 5],
                                      transactions[rep][9 * trns + 6], transactions[rep][9 * trns + 7],
                                      transactions[rep][9 * trns + 8]])
    senate_efds = pd.DataFrame(senate_trades,
                               columns=['first_name', 'last_name', 'report_title', 'date_filed', 'transaction_id',
                                        'transaction_date', 'security', 'company', 'security_type', 'transaction_type',
                                        'amount_range', 'comment'])
    # Write master data set to CSV
    senate_efds.to_csv('Senate EFDs.csv')


# Call functions as necessary
# scrape_senate_efds()      # Comment out to avoid lengthy scraping process when testing data manipulation
merge_data()
