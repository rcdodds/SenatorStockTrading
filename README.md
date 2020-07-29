# Senator Stock Trading

Whenever a US Senator or a member of their immediate family buys/sells personal financial assests (e.g. stocks, bonds, options, etc), the transaction must be reported and is freely available to the public at https://efdsearch.senate.gov/search/home/. This 

## Current State
This project currently uses Python Selenium to scrape that website and store the data in a SQLite database.
To improve runtimes, the script only considers reports that were filed on/after the most recent file date already present in the SQLite database.

## Possible Improvements
Future plans for this project would almost certainly involve integrating with stock market data.
This could be used to detect insider trading patterns, determine rates of returns,   

## Limitations
As with any project, the output is only as good as the input.
Some of the older electronic financial disclosures (EFDs) were filed as PDFs which cannot be scraped via this method.
The data contained at the transactional level is surprisingly vague. The amount of each transaction is a range (e.g. $1,001 - $15,000 or $50,001 - $100,000). There is no record of the price that the security was bought/sold for or the time of day that the transaction occured.


#### Terms & Conditions
By accessing the data contained in these reports you inherently agree to the following terms and conditions

Title 1 of the Ethics in Government Act of 1978, as amended, 5 U.S.C. app. § 105(c), states that:

It shall be unlawful for any person to obtain or use a report:
for any unlawful purpose;
for any commercial purpose, other than by news and communications media for dissemination to the general public;
for determining or establishing the credit rating of any individual; or
for use, directly or indirectly, in the solicitation of money for any political, charitable, or other purpose.

The Attorney General may bring a civil action against any person who obtains or uses a report for any purpose prohibited in paragraph (1) of this subsection. The court in which such action is brought may assess against such person a penalty in any amount not to exceed $10,000. Such remedy shall be in addition to any other remedy available under statutory or common law.

I understand the prohibitions on obtaining and use of financial disclosure reports.
