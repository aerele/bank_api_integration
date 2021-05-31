## Banking API Integration
Frappe application to achieve banking api integration.

Reach us out at hello@aerele.in to connect with our team.

#### License

GNU/General Public License (v3) (see [license.txt](license.txt))

The Apparelo code is licensed as GNU General Public License (v3) and the copyright is owned by Aerele Technologies Pvt Ltd (Aerele) and Contributors.

Here, OBP means ```Outward bank payment``` and BOBP means ```Bulk outward bank payment```

## Installation
Navigate to your bench folder
```
cd frappe-bench
```
Install Banking API Integration App
```
bench get-app bank_api_integration https://github.com/aerele/bank_api_integration.git
bench --site [site-name] install-app bank_api_integration
```

### Roles and it's permissions

1. Bank Maker - Able to create OBP and BOBP records.
2. Bank Checker - Able to approve or reject OBP and BOBP records.

### Securities Used

1. Password based security
2. OTP based transaction initiation

## Doctypes

### Bank API Integration

1. Each bank account should be linked to an bank api integration document in order to access various api's provided by the bank.
2. Enabling password security adds an extra layer of security before initiating a transaction via BOBP and OBP.
3. The ```Test``` API Provider can be used to test the entire flow. For the ```unique id``` values of various responses, please see the ```get_transaction_status``` function in the [Test API provider implementation](https://github.com/aerele/bankingapi/blob/master/banking_api/test.py)

![integration](https://user-images.githubusercontent.com/36359901/120153811-caa2e000-c20c-11eb-86a9-a9ee387d4f07.gif)

### Bulk Outward Bank Payment

1. Select appropriate options to use this doctype to process bulk payments.
2. In ```Outward Bank Payment Details```, upload the payment details as a CSV or Excel file.
3. Once you've saved, you'll see the total number of payments and total payment amount.

![bobp](https://user-images.githubusercontent.com/36359901/120153916-e908db80-c20c-11eb-8c9d-bfb7818940ec.jpg)

#### Bulk Outward Bank Payment Summary

![bobp_summary](https://user-images.githubusercontent.com/36359901/120164554-5706d000-c218-11eb-962b-6543ecf0e26e.jpg)


### Outward Bank Payment

Select appropriate options to use this doctype to process single payment.

![obp](https://user-images.githubusercontent.com/36359901/120153951-f3c37080-c20c-11eb-8d3a-3fbf8f7b3422.jpg)

#### Reject Flow

While rejecting payment, the user need to enter the reason for rejection

![reject](https://user-images.githubusercontent.com/36359901/120154070-1786b680-c20d-11eb-89ef-ca300c49ad64.jpg)

#### 

After approval of payment, the user needs to enter verification details before initiating the transaction.

![verification](https://user-images.githubusercontent.com/36359901/120154088-1ce40100-c20d-11eb-9f13-6b934cd96930.jpg)


### Bank API Request Log

For every API request, logs will be created automatically.

![request log](https://user-images.githubusercontent.com/36359901/120154032-0b025e00-c20d-11eb-958a-20cdf67baa59.jpg)

### Site Config JSON Details

Add the below details to the ```site_config.json``` of the site that has Bank API Integration.
```
"bank_api_integration": {
  "disable_transaction": [],
  "enable_otp_based_transaction": "*",
  "proxies": {
   "ftp": "ftp://112.22.158.85:3001",
   "http": "http://112.22.158.85:3001",
   "https": "https://112.22.158.85:3001"
  }
 }
 ```
 
1. Disable Transaction - Add "*" if you want to disable transaction for all bank accounts otherwise just include the account number's in a list like ```[123243234324,324324324]```

2. Enable OTP Based Transaction - Add "*" if you want to enable otp based transaction for all bank accounts otherwise just include the account number's in a list like  ```[123243234324,324324324]```

3. Adding proxies will allow making API requests from different IP's.

** Note: Malicious activities can be avoided by disabling the server script for the site that has Bank API Integration.

### Show some ❤️ by starring :star: :arrow_up: our repo!