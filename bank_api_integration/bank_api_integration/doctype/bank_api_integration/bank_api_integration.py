# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from six import string_types
from frappe import _
from frappe.model.document import Document
from banking_api import CommonProvider
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property
from frappe.core.doctype.version.version import get_diff
from frappe.utils import getdate, now_datetime, get_link_to_form, get_datetime

class BankAPIIntegration(Document):
	pass

def initiate_transaction_with_otp(docname, otp):
	doc = frappe.get_doc('Outward Bank Payment', docname)
	workflow_state = None

	res = None
	currency = frappe.db.get_value("Company", doc.company, "default_currency")
	prov, config = get_api_provider_class(doc.company_bank_account)
	filters = {
		"CUSTOMERINDUCED": "N",
		"REMARKS": doc.remarks,
		"OTP": otp,
		"UNIQUEID": doc.name,
		"IFSC": frappe.db.get_value('Bank Account', 
				{'party_type': doc.party_type,
				'party': doc.party,
				'is_default': 1
				},'ifsc_code'),
		"AMOUNT": str(doc.amount),
		"CURRENCY": currency,
		"TXNTYPE": doc.transaction_type,
		"PAYEENAME": doc.party,
		"DEBITACC": frappe.db.get_value('Bank Account', 
					{
					'name': doc.company_bank_account
					},'bank_account_no'),
		"CREDITACC": frappe.db.get_value('Bank Account', 
				{'party_type': doc.party_type,
				'party': doc.party,
				'is_default': 1
				},'bank_account_no')
	}
	try:
		res = prov.initiate_transaction_with_otp(filters)
		if res['status'] == 'SUCCESS' and 'utr_number' in res:
			frappe.db.set_value('Outward Bank Payment',{'name':doc.name},'utr_number',res['utr_number'])
			frappe.db.set_value(doc.doctype,{'name':doc.name},'is_verified',1)
			workflow_state = 'Initiated'
		elif res['status'] in ['FAILURE', 'DUPLICATE']:
			workflow_state = 'Initiation Failed'
		elif 'PENDING' in res['status']:
			workflow_state = 'Initiation Pending'
		elif res['status'] in ['OTP EXPIRED', 'INVALID OTP']:
			workflow_state = None
		else:
			workflow_state = 'Initiation Error'
	except:
		workflow_state = 'Initiation Error'
		res = frappe.get_traceback()
	log_name = log_request(doc.name, 'Initiate Transaction with OTP', filters, config, res)
	if not workflow_state:
		status = res['status']
		frappe.throw(_(f'{status}'))
	if workflow_state:
		frappe.db.set_value('Outward Bank Payment', {'name': doc.name}, 'workflow_state', workflow_state)
		frappe.db.commit()
	if workflow_state in ['Initiation Error', 'Initiation Failed']:
		if not doc.bobp:
			frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))

def initiate_transaction_without_otp(docname):
	doc = frappe.get_doc('Outward Bank Payment', docname)
	workflow_state = None

	res = None
	currency = frappe.db.get_value("Company", doc.company, "default_currency")
	prov, config = get_api_provider_class(doc.company_bank_account)
	filters = {
		"REMARKS": doc.remarks,
		"UNIQUEID": doc.name,
		"IFSC": doc.ifsc_code,
		"AMOUNT": str(doc.amount),
		"CURRENCY": currency,
		"TXNTYPE": doc.transaction_type,
		"PAYEENAME": doc.party,
		"DEBITACC": doc.debit_acc,
		"CREDITACC": doc.bank_account_no,
	}
	try:
		res = prov.initiate_transaction_without_otp(filters)
		if res['status'] == 'SUCCESS' and 'utr_number' in res:
			frappe.db.set_value('Outward Bank Payment',{'name':doc.name},'utr_number',res['utr_number'])
			frappe.db.set_value(doc.doctype,{'name':doc.name},'is_verified',1)
			workflow_state = 'Initiated'
		elif res['status'] in ['FAILURE', 'DUPLICATE']:
			workflow_state = 'Initiation Failed'
		elif 'PENDING' in res['status']:
			workflow_state = 'Initiation Pending'
		else:
			workflow_state = 'Initiation Error'
	except:
		workflow_state = 'Initiation Error'
		res = frappe.get_traceback()
	log_name = log_request(doc.name, 'Initiate Transaction without OTP', filters, config, res)
	if workflow_state:
		frappe.db.set_value('Outward Bank Payment', {'name': doc.name}, 'workflow_state', workflow_state)
		frappe.db.commit()
	if workflow_state in ['Initiation Error', 'Initiation Failed']:
		if not doc.bobp:
			frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))

@frappe.whitelist()
def send_otp(doctype, docname):
	is_otp_sent = False
	res = None
	doc = frappe.get_doc(doctype, docname)
	prov, config = get_api_provider_class(doc.company_bank_account)
	if doc.doctype == 'Bulk Outward Bank Payment':
		row = vars(doc.outward_bank_payment_details[0])
		data = {
			'party_type': row['party_type'],
			'party': row['party'],
			'amount': row['amount'],
			'remarks': doc.remarks,
			'transaction_type': doc.transaction_type,
			'company_bank_account': doc.company_bank_account,
			'reconcile_action': doc.reconcile_action,
			'bobp':doc.name}
		if not frappe.db.exists('Outward Bank Payment', data):
			data['doctype'] = 'Outward Bank Payment'
			obp_doc = frappe.get_doc(data)
			obp_doc.save(ignore_permissions=True)
			obp_doc.submit()
			status = frappe.db.get_value('Outward Bank Payment', obp_doc.name, 'workflow_state')
			frappe.db.set_value('Outward Bank Payment Details',{'parent':doc.name,
				'party_type': row['party_type'],
				'party': row['party'],
				'amount': row['amount']},'outward_bank_payment',obp_doc.name)
			frappe.db.set_value('Outward Bank Payment Details',{'parent':doc.name,
				'party_type': row['party_type'],
				'party': row['party'],
				'amount': row['amount'],
				'outward_bank_payment':obp_doc.name},'status', status)
			doc = obp_doc
	filters = {
		"UNIQUEID": doc.name,
		"AMOUNT": str(doc.amount)
	}
	try:
		res = prov.send_otp(filters)
		if res['status'] == 'SUCCESS':
			is_otp_sent = True
	except:
		res = frappe.get_traceback()
	log_name = log_request(doc.name,'Send OTP', filters, config, res)
	if not is_otp_sent:
		retry_count = frappe.db.get_value(doc.doctype, doc.name, 'retry_count')
		workflow_state = frappe.db.get_value(doc.doctype, doc.name, 'workflow_state')
		if workflow_state == 'Approved' and retry_count == 3:
			frappe.db.set_value(doc.doctype, doc.name, 'workflow_state', 'Verification Failed')
	return is_otp_sent

@frappe.whitelist()
def update_transaction_status(obp_name=None,bobp_name=None):
	bulk_update = True
	if obp_name or bobp_name:
		bulk_update = False
	if obp_name:
		obp_list = [{'name': obp_name}]
	if bobp_name:
		obp_list = frappe.db.get_all('Outward Bank Payment', {'workflow_state': ['in', ['Initiated','Initiation Pending','Transaction Pending']], 'bobp': ['=', bobp_name]})
	if bulk_update:
		obp_list = frappe.db.get_all('Outward Bank Payment', {'workflow_state': ['in', ['Initiated','Initiation Pending','Transaction Pending']]})

	failed_obp_list = []
	if not obp_list:
		frappe.throw(_("No transaction found in the initiated state."))
	for doc in obp_list:
		res = None
		workflow_state = None
		obp_doc = frappe.get_doc('Outward Bank Payment', doc['name'])
		prov, config = get_api_provider_class(obp_doc.company_bank_account)
		unique_id = frappe.db.get_value('Bank API Integration', 
			{'bank_account': obp_doc.company_bank_account}, 'unique_id')
		filters = {"UNIQUEID": obp_doc.name if not unique_id else unique_id}
		try:
			res = prov.get_transaction_status(filters)
			if res['status'] == 'SUCCESS' and 'utr_number' in res:
				workflow_state = 'Transaction Completed'
			elif res['status'] in ['FAILURE', 'DUPLICATE']:
				workflow_state = 'Transaction Failed'
			elif 'PENDING' in res['status']:
				workflow_state = 'Transaction Pending'
			else:
				workflow_state = 'Transaction Error'
		except:
			# workflow_state = 'Transaction Error'
			res = frappe.get_traceback()
		
		log_name = log_request(obp_doc.name,'Update Transaction Status', filters, config, res)
		# obp_doc.workflow_state = workflow_state
		# obp_doc.save()
		if workflow_state:
			frappe.db.set_value('Outward Bank Payment', {'name': obp_doc.name}, 'workflow_state', workflow_state)
			frappe.db.commit()
		if workflow_state in ['Transaction Pending', 'Transaction Error', 'Transaction Failed'] and not bulk_update:
			if not obp_doc.bobp:
				frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))
			else:
				failed_obp_list.append(get_link_to_form("Outward Bank Payment", doc['name']))
	if failed_obp_list and not bulk_update:
		failed_obp = ','.join(failed_obp_list)
		frappe.throw(_(f"Transaction status update failed for the below obp(s) {failed_obp}"))
	if bobp_name and not bulk_update:
		frappe.msgprint(_("Transaction Status Updated"))

def get_api_provider_class(company_bank_account):
	config = frappe.get_site_config()
	proxies = None
	if not frappe.db.get_value('Bank API Integration', {'bank_account': company_bank_account, 'enable':1}):
		frappe.throw(_(f'Kindly create and enable bank api integration for this bank account {get_link_to_form("Bank Account", company_bank_account)}'))
	integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': company_bank_account, 'enable':1})	
	if 'bank_api_integration' in config:
		proxies = config.bank_api_integration['proxies'] \
			if 'proxies' in config.bank_api_integration else None
	config = {"APIKEY": integration_doc.get_password(fieldname="api_key") if integration_doc.api_key else None, 
			"CORPID": integration_doc.corp_id,
			"USERID": integration_doc.user_id,
			"AGGRID":integration_doc.aggr_id,
			"AGGRNAME":integration_doc.aggr_name,
			"URN": integration_doc.urn}
	
	file_paths = {'private_key': integration_doc.get_password(fieldname="private_key_path") if integration_doc.private_key_path else None,
		'public_key': frappe.local.site_path + integration_doc.icici_public_key if integration_doc.icici_public_key else None}
	
	prov = CommonProvider(integration_doc.bank_api_provider, config, integration_doc.use_sandbox, proxies, file_paths, frappe.local.site_path)
	return prov, config

def new_bank_transaction(transaction_list, bank_account):
	for transaction in transaction_list:
		if not frappe.db.exists("Bank Transaction", dict(transaction_id=transaction["txn_id"])):
			new_transaction = frappe.get_doc({
				'doctype': 'Bank Transaction',
				'date': getdate(transaction['txn_date'].split(' ')[0]),
				"transaction_id": transaction["txn_id"],
				'withdrawal': abs(float(transaction['debit'].replace(',',''))) if transaction['debit'] else 0,
				'deposit': abs(float(transaction['credit'].replace(',',''))) if transaction['credit'] else 0,
				'description': transaction['remarks'],
				'bank_account': bank_account
			})
			new_transaction.save()
			new_transaction.submit()
	return True

@frappe.whitelist()
def fetch_balance(bank_account = None):
	account_list = []
	
	if not bank_account:
		for acc in frappe.db.get_list('Bank Account', {'is_company_account': 1}):
			account_list.append(acc['name'])
	else:
		account_list.append(bank_account)

	for acc in account_list:
		prov, config = get_api_provider_class(acc)
		filters = {
			"ACCOUNTNO": frappe.db.get_value('Bank Account',{'name':acc},'bank_account_no')
		}
		try:
			res = prov.fetch_balance(filters)
			doc = frappe.get_doc('Bank Account', acc)
			if res['status'] == 'SUCCESS':
				doc.db_set('balance_amount',res['balance'])
				doc.db_set('balance_last_synced_on',get_datetime(res['date']))
				doc.reload()
				frappe.msgprint(_("""Balance Updated"""))
		except:
			res = frappe.get_traceback()
		
		log_name = log_request(bank_account, 'Fetch Balance', filters, config, res)
		if isinstance(res, dict):
			if 'status' in res and res['status']== 'FAILURE' and bank_account:
				frappe.throw(_(f'Unable to fetch balance.Please check log {get_link_to_form("Bank API Request Log", log_name)} for more info.'))
		else:
			if bank_account:
				frappe.throw(_(f'Unable to fetch balance.Please check log {get_link_to_form("Bank API Request Log", log_name)} for more info.'))

@frappe.whitelist()
def fetch_account_statement(bank_account = None):
	account_list = []
	
	if not bank_account:
		for acc in frappe.db.get_list('Bank Account', {'is_company_account': 1}):
			account_list.append(acc['name'])
	else:
		account_list.append(bank_account)

	for acc in account_list:
		prov, config = get_api_provider_class(acc)
		now_date = now_datetime().strftime("%d-%m-%Y")
		try:
			last_doc = frappe.get_last_doc("Bank Transaction", {'bank_account':acc})
			from_date = last_doc.date.strftime("%d-%m-%Y")
			if not from_date:
				from_date = now_date
		except:
			from_date = now_date
		filters = {
			"ACCOUNTNO": frappe.db.get_value('Bank Account',{'name':acc},'bank_account_no'),
			"FROMDATE": from_date,
			"TODATE": now_date
		}
		try:
			res = prov.fetch_statement(filters)
			doc = frappe.get_doc('Bank Account', acc)
			if res['status'] == 'SUCCESS':
				transaction_list = []
				for transaction in res['record']:
					credit = 0 
					debit = 0
					if transaction['TYPE'] == 'DR':
						debit = transaction['AMOUNT']
					if transaction['TYPE'] == 'CR':
						credit = transaction['AMOUNT']

					transaction_list.append({
						'txn_id': transaction['TRANSACTIONID'],
						'txn_date':transaction['TXNDATE'],
						'debit': debit,
						'credit': credit,
						'remarks':transaction['REMARKS']
					})
				if new_bank_transaction(transaction_list, acc):
					doc.db_set('statement_last_synced_on',now_datetime())
					doc.reload()
					frappe.msgprint(_("""Statements updated"""))
		except:
			res = frappe.get_traceback()
		
		log_name = log_request(bank_account, 'Fetch Account Statement', filters, config, res)
		if isinstance(res, dict):
			if 'status' in res and res['status']== 'FAILURE' and bank_account:
				frappe.throw(_(f'Unable to fetch statement.Please check log {get_link_to_form("Bank API Request Log", log_name)} for more info.'))
		else:
			frappe.throw(_(f'Unable to fetch statement.Please check log {get_link_to_form("Bank API Request Log", log_name)} for more info.'))

def log_request(doc_name, api_method, filters, config, res):
	request_log = frappe.get_doc({
		"doctype": "Bank API Request Log",
		"user": frappe.session.user,
		"reference_document":doc_name,
		"api_method": api_method,
		"filters": json.dumps(filters, indent=4) if filters else None,
		"config_details": json.dumps(config, indent=4),
		"response": json.dumps(res, indent=4)
	})
	request_log.save(ignore_permissions=True)
	frappe.db.commit()
	return request_log.name

def create_defaults():
	#Create default roles
	roles = ['Bank Maker','Bank Checker']
	for role in roles:
		if not frappe.db.exists('Role', role):
			role_doc = frappe.new_doc("Role")
			role_doc.role_name = role
			role_doc.save()

	#Create custom field
	custom_fields = {
	'Bank Account': [
	{
		"fieldname": "ifsc_code",
		"fieldtype": "Data",
		"label": "IFSC Code",
		"insert_after" : "iban"
	},
	{
		"fieldname": "account_statemnt_and_balance_details",
		"fieldtype": "Section Break",
		"label": "Account Statement and Balance Details",
		"insert_after" : "mask",
		"depends_on": "eval: doc.is_company_account == 1 && !doc.__islocal"
	},
	{
		"fieldname": "fetch_balance",
		"fieldtype": "Button",
		"label": "Fetch Balance",
		"insert_after" : "account_statemnt_and_balance_details"
	},
	{
		"fieldname": "balance_amount",
		"fieldtype": "Float",
		"label": "Balance Amount",
		"insert_after" : "fetch_balance",
		"read_only": 1
	},
	{
		"fieldname": "balance_last_synced_on",
		"fieldtype": "Datetime",
		"label": "Balance Last Synced On",
		"insert_after" : "balance_amount",
		"read_only": 1
	},
	{
		"fieldname": "column_break_30",
		"fieldtype": "Column Break",
		"insert_after" : "balance_last_synced_on"
	},
	{
		"fieldname": "fetch_account_statement",
		"fieldtype": "Button",
		"label": "Fetch Account Statement",
		"insert_after" : "column_break_30"
	},
	{
		"fieldname": "statement_last_synced_on",
		"fieldtype": "Datetime",
		"label": "Statement Last Synced On",
		"insert_after" : "fetch_account_statement",
		"read_only": 1
	}
	]}
	create_custom_fields(
		custom_fields, ignore_validate=frappe.flags.in_patch, update=True)

	#Create workflow state
	states_with_style = {'Success': ['Verified','Initiated', 'Transaction Completed', 'Completed'],
	'Danger': ['Verification Failed', 'Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Transaction Error', 'Failed'],
	'Primary': ['Transaction Pending', 'Initiation Pending', 'Processing', 'Partially Completed']}

	for style in states_with_style.keys():
		for state in states_with_style[style]:
			if not frappe.db.exists('Workflow State', state):
				frappe.get_doc({"doctype" : "Workflow State",
								"workflow_state_name" : state,
								"style" : style}).save()

	create_workflow('Outward Bank Payment')
	create_workflow('Bulk Outward Bank Payment')
	set_permissions_to_core_doctypes()

def create_workflow(document_name):
	#Create default workflow
	if not frappe.db.exists('Workflow', f'{document_name} Workflow'):
		workflow_doc = frappe.get_doc({'doctype': 'Workflow',
				'workflow_name': f'{document_name} Workflow',
				'document_type': document_name,
				'workflow_state_field': 'workflow_state',
				'is_active': 1,
				'send_email_alert':0})

		workflow_doc.append('states',{'state': 'Pending',
					'doc_status': 0,
					'update_field': 'workflow_state',
					'update_value': 'Pending',
					'allow_edit': 'Bank Maker'})

		pending_next_states = [['Approve', 'Approved'], ['Reject', 'Rejected']]
		for state in pending_next_states:
			workflow_doc.append('states',{'state': state[1],
						'doc_status': 1,
						'update_field': 'workflow_state',
						'update_value': state[1],
						'allow_edit': 'Bank Checker'})
			transitions = { 'state': 'Pending',
							'action': state[0],
							'allow_self_approval': 0,
							'next_state': state[1],
							'allowed': 'Bank Checker'}
			workflow_doc.append('transitions',transitions)	
		if document_name == 'Outward Bank Payment':
			optional_states = ['Verified','Verification Failed','Initiated',
					'Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Initiation Pending',
					'Transaction Error', 'Transaction Pending', 'Transaction Completed']
		if document_name == 'Bulk Outward Bank Payment':
			optional_states = ['Verified','Verification Failed','Initiated', 'Processing', 'Partially Completed', 'Completed', 'Failed']

		for state in optional_states:
			workflow_doc.append('states',{'state': state,
					'is_optional_state': 1,
					'doc_status': 1,
					'update_field': 'workflow_state',
					'update_value': state,
					'allow_edit': 'Bank Checker'})

		workflow_doc.save()

def set_permissions_to_core_doctypes():
	roles = ['Bank Checker', 'Bank Maker']
	core_doc_list = ['Bank Account', 'Company', 'Supplier', 'Customer', 'Employee']

	# assign select permission
	for role in roles:
		for doc in core_doc_list:
			add_permission(doc, role, 0)
			update_permission_property(doc, role, 0, 'select', 1)

def is_authorized(new_doc):
	old_doc = new_doc.get_doc_before_save()
	if old_doc:
		diff = get_diff(old_doc, new_doc)
		if diff:
			for changed in diff.changed:
				field, old, new = changed
				if field in ['is_verified', 'retry_count']:
					frappe.throw('Unauthorized Access')
	elif new_doc.is_verified or new_doc.retry_count:
		frappe.throw('Unauthorized Access')
	else:
		return

@frappe.whitelist()
def get_company_bank_account(doctype, txt, searchfield, start, page_len, filters):
	bank_accounts = []
	for acc in frappe.get_list("Bank Account", filters= filters,fields=["name"]):
		if not acc['name'] in bank_accounts:
			is_enabled = frappe.get_value('Bank API Integration', 
				{'bank_account': acc['name']}, 
				'enable_transaction')
			if is_enabled:
				bank_accounts.append([acc['name']])
	return bank_accounts

@frappe.whitelist()
def get_transaction_type(bank_account):
	common_transaction_types = ['RTGS', 'NEFT', 'IMPS']
	mappings = {
		'ICICI': ['Internal Payments', 'External Payments', 'Virtual A/c Payments']
	}
	bank_api_provider = frappe.get_value('Bank API Integration', {'bank_account': bank_account}, 'bank_api_provider')
	
	if not bank_api_provider in mappings:
		return common_transaction_types
	return common_transaction_types + mappings[bank_api_provider]

@frappe.whitelist()
def get_field_status(bank_account):
	config = frappe.get_site_config()
	data = {}
	if 'bank_api_integration' in config:
		enable_otp_based_transaction = config.bank_api_integration['enable_otp_based_transaction'] \
			if 'enable_otp_based_transaction' in config.bank_api_integration else None
		acc_num = frappe.get_value('Bank Account', {'name': bank_account},'bank_account_no')
		is_pwd_security_enabled = frappe.get_value("Bank API Integration", {"bank_account": bank_account}, "enable_password_security")
		disabled_accounts = config.bank_api_integration['disable_transaction'] \
			if 'disable_transaction' in config.bank_api_integration else None
		if disabled_accounts and (disabled_accounts == '*' or acc_num in disabled_accounts):
			frappe.throw(_(f'Unable to process transaction for the selected bank account. Please contact Administrator.'))
			return

		if enable_otp_based_transaction and (enable_otp_based_transaction == '*' or acc_num in enable_otp_based_transaction):
			data['is_otp_enabled'] = 1
		if is_pwd_security_enabled:
			data['is_pwd_security_enabled'] = 1
	else:
		data['is_otp_enabled'] = 1
	return data

@frappe.whitelist()
def update_status(doctype_name,docname, status):
	frappe.db.set_value(doctype_name, {'name': docname}, 'docstatus', 1)
	frappe.db.set_value(doctype_name, {'name': docname}, 'workflow_state', status)

@frappe.whitelist()
def verify_and_initiate_transaction(doc, entered_password=None, otp=None):
	if isinstance(doc, string_types):
		doc = frappe._dict(json.loads(doc))
	obp_doc_name = doc['name']
	retry_count = doc['retry_count'] + 1
	frappe.db.set_value(doc['doctype'], doc['name'], 'retry_count', retry_count)
	if doc['doctype'] == 'Bulk Outward Bank Payment':
		row = doc['outward_bank_payment_details'][0]
		data = {
			'party_type': row['party_type'],
			'party': row['party'],
			'amount': row['amount'],
			'remarks': doc['remarks'],
			'transaction_type': doc['transaction_type'],
			'company_bank_account': doc['company_bank_account'],
			'reconcile_action': doc['reconcile_action'],
			'bobp': doc['name']}
		obp_doc_name = frappe.db.exists('Outward Bank Payment', data)
		if not obp_doc_name:
			data['doctype'] = 'Outward Bank Payment'
			obp_doc = frappe.get_doc(data)
			obp_doc.save(ignore_permissions=True)
			obp_doc.submit()
			status = frappe.db.get_value('Outward Bank Payment', obp_doc.name, 'workflow_state')
			frappe.db.set_value('Outward Bank Payment Details',{'parent':doc['name'],
				'party_type': row['party_type'],
				'party': row['party'],
				'amount': row['amount']},'outward_bank_payment',get_link_to_form('Outward Bank Payment', obp_doc.name))
			frappe.db.set_value('Outward Bank Payment Details',{'parent':doc['name'],
				'party_type': row['party_type'],
				'party': row['party'],
				'amount': row['amount'],
				'outward_bank_payment':obp_doc.name},'status', status)
			obp_doc_name = obp_doc.name

	if entered_password and otp:
		integration_doc_name = frappe.get_value('Bank API Integration',{'bank_account': doc['company_bank_account']},'name')
		defined_password = frappe.utils.password.get_decrypted_password('Bank API Integration', integration_doc_name, fieldname='transaction_password')
		if not entered_password == defined_password:
			frappe.throw(_("Invalid Password"))
		initiate_transaction_with_otp(obp_doc_name, otp)

	if entered_password and not otp:
		integration_doc_name = frappe.get_value('Bank API Integration',{'bank_account': doc['company_bank_account']},'name')
		defined_password = frappe.utils.password.get_decrypted_password('Bank API Integration', integration_doc_name, fieldname='transaction_password')
		if not entered_password == defined_password:
			frappe.throw(_("Invalid Password"))
		initiate_transaction_without_otp(obp_doc_name)

	if otp and not entered_password:
		initiate_transaction_with_otp(obp_doc_name, otp)

	retry_count = frappe.db.get_value(doc['doctype'], doc['name'], 'retry_count')
	workflow_state = frappe.db.get_value('Outward Bank Payment', obp_doc_name, 'workflow_state')
	if workflow_state == 'Approved' and retry_count == 3:
		frappe.db.set_value(doc.doctype, doc.name, 'workflow_state', 'Verification Failed')

	if workflow_state in ['Initiated', 'Initiation Pending']:
		if doc['doctype'] == 'Bulk Outward Bank Payment':
			bobp = frappe.get_doc('Bulk Outward Bank Payment', doc['name'])
			bobp.bulk_create_obp_records()