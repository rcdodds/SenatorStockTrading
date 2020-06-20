# A script to track recent stock trades by Congress members
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import time
import csv
import os.path
from os import path


# Open the webpage
url = 'https://efdsearch.senate.gov/search/'
DRIVER_PATH = 'C:\\bin\chromedriver.exe'
driver = webdriver.Chrome(executable_path=DRIVER_PATH)
driver.get(url)

# Agree not to use the data for anything illegal
agree_checkbox = driver.find_element_by_id('agree_statement')
agree_checkbox.click()


report_links = ['https://efdsearch.senate.gov/search/view/ptr/c6302d00-ca70-47b4-82be-71cbd2c0ecf5/','https://efdsearch.senate.gov/search/view/ptr/bc5764cd-d819-4508-bfda-8b3931bcfeb6/']
report_transactions = []

for report_link in report_links:
    driver.get(report_link)
    report_transactions.append([cell.text.replace('\n' ,' ')  for cell in driver.find_elements_by_xpath('.//td')])
    print(report_transactions)
    print(len(report_transactions))
