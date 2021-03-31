# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider
from frappe.utils import today
from six import string_types
from frappe.utils import get_site_path
from erpnext.accounts.doctype.payment_entry.payment_entry import get_negative_outstanding_invoices, get_orders_to_be_billed
from erpnext.controllers.accounts_controller import get_supplier_block_status
from erpnext.accounts.utils import get_outstanding_invoices, get_account_currency

class OutwardBankPayment(Document):
	# def on_change(self):
	# 	if self.reconcile_action == 'Auto Reconcile Oldest First Invoice' and self.status == 'Transaction Completed':
	# 		self.create_payment_entry()

	# def create_payment_entry(self):
	# 	payment_entry_dict = {
	# 		"company" : self.company,
	# 		"payment_type" : 'Pay',
	# 		"mode_of_payment": 'Wire Transfer',
	# 		"party_type" :  self.party_type,
	# 		"party" :  self.party,
	# 		"posting_date" : today(),
	# 		"paid_amount": self.amount
	# 	}
	# 	payment_entry = frappe.new_doc("Payment Entry")
	# 	payment_entry.update(payment_entry_dict)

	# 	payment_entry.insert()
	# 	payment_entry.submit()

	# 	return payment_entry.name

	def on_submit(self):
		if self.workflow_state == 'Approved':
			res = None
			currency = frappe.db.get_value("Company", self.company, "default_currency")
			prov, config = self.get_api_provider_class()
			print(prov)
			integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': self.company_bank_account})
			filters = {
				"UNIQUEID": self.name,
				"IFSC": integration_doc.ifsc,
				"AMOUNT": self.amount,
				"CURRENCY": currency,
				"TXNTYPE": self.transaction_type,
				"PAYEENAME": self.party,
				"DEBITACC": integration_doc.account_number,
				"CREDITACC": "000405002777",
				"WORKFLOW_REQD": "N"

			}
			try:
				res = prov.initiate_transaction_without_otp(filters)
				res['status'] = 'Error'
				if res['status'] == 'Success':
					self.status = 'Initiated'
					self.workflow_state = 'Initiated'
				if res['status'] == 'Failed':
					self.status = 'Initiation Failed'
					self.workflow_state = 'Initiation Failed'
					self.error_message = f'Initiate Transaction API Failed: {msg}'
				if res['status'] == 'Error':
					self.status = 'Initiation Error'
					self.workflow_state = 'Initiation Error'
					self.error_message = f'Initiate Transaction API Error: {msg}'
			except:
				self.status = 'Initiation Error'
				self.workflow_state = 'Initiation Error'
				res = frappe.get_traceback()
			log_name = self.log_request('Initiate Transaction without OTP', filters, config, res)
			self.save()
			self.reload()
			if self.status == 'Initiation Error':
				frappe.throw(_(f'Kindly check request log for more info {log_name}'))


	def get_api_provider_class(self):
		integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': self.company_bank_account})
		proxies = frappe.get_site_config().proxies
		config = {"APIKEY": integration_doc.get_password(fieldname="api_key"), 
				"CORPID": integration_doc.corp_id,
				"USERID": integration_doc.user_id,
				"AGGRID":integration_doc.aggr_id,
				"AGGRNAME":integration_doc.aggr_name,
				"URN": integration_doc.urn}
		
		file_paths = {'private_key': integration_doc.get_password(fieldname="private_key_path"),
			'public_key': frappe.local.site_path + integration_doc.public_key_attachment}
		
		prov = CommonProvider(integration_doc.bank_api_provider, config, integration_doc.use_sandbox, proxies, file_paths)
		return prov, config

	def log_request(self, api_method, filters, config, res):
		request_log = frappe.get_doc({
			"doctype": "Bank API Request Log",
			"user": frappe.session.user,
			"reference_document": self.name,
			"api_method": api_method,
			"filters": str(filters) if filters else None,
			"config_details": str(config),
			"response": res
		})
		request_log.save(ignore_permissions=True)
		frappe.db.commit()
		return request_log.name

# def initiate_transaction(provider_name, config_info, use_sandbox, proxy_dict, file_paths):
# 	prov = CommonProvider(provider_name, config_info, use_sandbox, proxy_dict, file_paths)
# 	res = prov.initiate_transaction({})
# 	print(res)
# 	return res

# def update_transaction_status():
# 	settings  = frappe.get_single('Bank API Integration Settings')
# 	config_info = {'merchant_id': settings.merchant_id}
# 	prov = CommonProvider(settings.bank_api_provider, config_info)
# 	obp_list = frappe.db.get_all('Outward Bank Payment', {'status': ['in', ['Initiated','Transaction Error', 'Transaction Pending']]})
# 	for doc in obp_list:
# 		obp_doc = frappe.get_doc('Outward Bank Payment', doc['name'])
# 		if obp_doc.status == 'Initiated':
# 			obp_doc.retry_count = 0
# 			obp_doc.error_message = None
# 		else:
# 			obp_doc.retry_count +=1
# 		try:
# 			config_info['order_id'] = obp_doc.name
# 			res = prov.get_transaction_status()
# 			msg = res['msg']
# 			if res['status'] == 'Success':
# 				obp_doc.status = 'Transaction Completed'
# 				obp_doc.workflow_state = 'Transaction Completed'
# 			if res['status'] == 'Failed':
# 				obp_doc.status = 'Transaction Failed'
# 				obp_doc.workflow_state = 'Transaction Failed'
# 				obp_doc.error_message = f'Fetch Transaction Status API Failed: {msg}'
# 			if res['status'] == 'Pending':
# 				obp_doc.status = 'Transaction Pending'
# 				obp_doc.workflow_state = 'Transaction Pending'
# 				obp_doc.error_message = f'Transaction Pending: {msg}'			
# 		except:
# 			obp_doc.status = 'Transaction Error'
# 			obp_doc.workflow_state = 'Transaction Error'
# 			obp_doc.error_message = 'Fetch Transaction Status API Error: '+ frappe.get_traceback()
# 		obp_doc.save()

# def process_uninitiated_transaction():
# 	obp_list = frappe.db.get_all('Outward Bank Payment', {'status': 'Initiation Error','retry_count': ('<', 5)})
# 	for doc in obp_list:
# 		obp_doc = frappe.get_doc('Outward Bank Payment', doc['name'])
# 		currency = frappe.db.get_value("Company", obp_doc.company, "default_currency")
# 		try:
# 			config_info = {'order_id': obp_doc.name, 'user_info':{'cust_id':'XXX'}, 'txn_info':{'amount': obp_doc.amount,'currency': currency}}
# 			obp_doc.retry_count += 1
# 			res = initiate_transaction(config_info)
# 			msg = res['msg']
# 			if res['status'] == 'Success':
# 				obp_doc.status = 'Initiated'
# 				obp_doc.workflow_state = 'Initiated'
# 			if res['status'] == 'Failed':
# 				obp_doc.status = 'Initiation Failed'
# 				obp_doc.workflow_state = 'Initiation Failed'
# 				obp_doc.error_message = f'Initiate Transaction API Failed: {msg}'
# 			if res['status'] == 'Error':
# 				obp_doc.status = 'Initiation Error'
# 				obp_doc.workflow_state = 'Initiation Error'
# 				obp_doc.error_message = f'Initiate Transaction API Error: {msg}'
# 		except:
# 			obp_doc.status = 'Initiation Error'
# 			obp_doc.workflow_state = 'Initiation Error'
# 			obp_doc.error_message = 'Initiate Transaction API Error: '+frappe.get_traceback()
# 		obp_doc.save()

def initiate_transaction(provider_name, config_info, use_sandbox, proxy_dict, file_paths):
	prov = CommonProvider(provider_name, config_info, use_sandbox, proxy_dict, file_paths)
	res = prov.initiate_transaction({})
	return res

# def create_workflow_state():
# 	states = {'Initiated': 'Success', 'Initiation Error': 'Danger', 'Initiation Failed': 'Danger',
# 		'Transaction Error': 'Danger','Transaction Failed': 'Danger', 'Transaction Pending': 'Primary', 'Transaction Completed': 'Success'}
# 	for state in states.keys():
# 		if not frappe.db.exists("Workflow State", state):
# 			workflow_state=frappe.new_doc("Workflow State")
# 			workflow_state.style= states[state]
# 			workflow_state.save()

# @frappe.whitelist()
# def get_outstanding_reference_documents(args):

# 	if isinstance(args, string_types):
# 		args = json.loads(args)

# 	if args.get('party_type') == 'Member':
# 		return

# 	args['party_account'] =  frappe.db.get_value('Account', {'account_type': 'Payable','is_group': 0, 'company': args.get('company')})
# 	print(args)

# 	# confirm that Supplier is not blocked
# 	if args.get('party_type') == 'Supplier':
# 		supplier_status = get_supplier_block_status(args['party'])
# 		if supplier_status['on_hold']:
# 			if supplier_status['hold_type'] == 'All':
# 				return []
# 			elif supplier_status['hold_type'] == 'Payments':
# 				if not supplier_status['release_date'] or getdate(nowdate()) <= supplier_status['release_date']:
# 					return []

# 	party_account_currency = get_account_currency(args.get("party_account"))
# 	company_currency = frappe.get_cached_value('Company',  args.get("company"),  "default_currency")

# 	# Get negative outstanding sales /purchase invoices
# 	negative_outstanding_invoices = []
# 	if args.get("party_type") not in ["Student", "Employee"] and not args.get("voucher_no"):
# 		negative_outstanding_invoices = get_negative_outstanding_invoices(args.get("party_type"), args.get("party"),
# 			args.get("party_account"), args.get("company"), party_account_currency, company_currency)

# 	# Get positive outstanding sales /purchase invoices/ Fees
# 	condition = ""
# 	if args.get("voucher_type") and args.get("voucher_no"):
# 		condition = " and voucher_type={0} and voucher_no={1}"\
# 			.format(frappe.db.escape(args["voucher_type"]), frappe.db.escape(args["voucher_no"]))

# 	# Add cost center condition
# 	if args.get("cost_center"):
# 		condition += " and cost_center='%s'" % args.get("cost_center")

# 	date_fields_dict = {
# 		'posting_date': ['from_posting_date', 'to_posting_date'],
# 		'due_date': ['from_due_date', 'to_due_date']
# 	}

# 	for fieldname, date_fields in date_fields_dict.items():
# 		if args.get(date_fields[0]) and args.get(date_fields[1]):
# 			condition += " and {0} between '{1}' and '{2}'".format(fieldname,
# 				args.get(date_fields[0]), args.get(date_fields[1]))

# 	if args.get("company"):
# 		condition += " and company = {0}".format(frappe.db.escape(args.get("company")))

# 	outstanding_invoices = get_outstanding_invoices(args.get("party_type"), args.get("party"),
# 		args.get("party_account"), filters=args, condition=condition)

# 	for d in outstanding_invoices:
# 		d["exchange_rate"] = 1
# 		if party_account_currency != company_currency:
# 			if d.voucher_type in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
# 				d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
# 			elif d.voucher_type == "Journal Entry":
# 				d["exchange_rate"] = get_exchange_rate(
# 					party_account_currency,	company_currency, d.posting_date
# 				)
# 		if d.voucher_type in ("Purchase Invoice"):
# 			d["bill_no"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "bill_no")

# 	# Get all SO / PO which are not fully billed or aginst which full advance not paid
# 	orders_to_be_billed = []
# 	if (args.get("party_type") != "Student"):
# 		orders_to_be_billed =  get_orders_to_be_billed(args.get("posting_date"),args.get("party_type"),
# 			args.get("party"), args.get("company"), party_account_currency, company_currency, filters=args)

# 	data = negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed
# 	print(negative_outstanding_invoices, outstanding_invoices, orders_to_be_billed)
# 	if not data:
# 		frappe.msgprint(_("No outstanding invoices found for the {0} {1} which qualify the filters you have specified.")
# 			.format(args.get("party_type").lower(), frappe.bold(args.get("party"))))

# 	return data