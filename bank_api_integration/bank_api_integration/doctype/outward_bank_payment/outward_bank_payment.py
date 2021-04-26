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
from frappe.utils import add_months, nowdate
class OutwardBankPayment(Document):
	def on_change(self):
		if self.reconcile_action == 'Auto Reconcile Oldest First Invoice' and self.status == 'Transaction Completed':
			references = []
			amount = self.amount
			month_threshold = -6
			from_date = add_months(nowdate(), month_threshold)
			invoices = frappe.db.get_all('Purchase Invoice',{'supplier': self.party, 'posting_date': ['>=', from_date], 'posting_date': ['<=', nowdate()]}, ['grand_total', 'due_date', 'bill_no', 'name'])
			for inv in invoices:
				if inv['grand_total'] <= amount:
					references.append({
					'reference_doctype': 'Purchase Invoice',
					'reference_name': inv['name'],
					'bill_no': inv['bill_no'],
					'due_date': inv['due_date'],
					'total_amount': inv['grand_total']
					})
					amount-= inv['grand_total']
			self.create_payment_entry(references)
		if self.reconcile_action == 'Manual Reconcile' and self.status == 'Transaction Completed':
			references = []
			for row in self.payment_references:
				references.append({
				'reference_doctype': row.reference_doctype,
				'reference_name': row.reference_name,
				'bill_no': row.bill_no,
				'due_date': row.due_date,
				'total_amount': row.total_amount,
				'outstanding_amount': row.outstanding_amount,
				'allocated_amount': row.allocated_amount,
				'exchange_rate': row.exchange_rate
				})
			self.create_payment_entry(references)

	def create_payment_entry(self, references):
		payment_entry_dict = {
			"company" : self.company,
			"payment_type" : 'Pay',
			"mode_of_payment": 'Wire Transfer',
			"party_type" :  self.party_type,
			"party" :  self.party,
			"posting_date" : today(),
			"paid_amount": self.amount,
			"references": references
		}
		payment_entry = frappe.new_doc("Payment Entry")
		payment_entry.update(payment_entry_dict)

		payment_entry.insert()
		payment_entry.submit()

		self.payment_entry = payment_entry.name
		self.save()
		self.reload()

	def on_submit(self):
		if self.workflow_state == 'Approved':
			res = None
			currency = frappe.db.get_value("Company", self.company, "default_currency")
			prov, config = self.get_api_provider_class()
			integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': self.company_bank_account})
			filters = {
				"UNIQUEID": self.name,
				"IFSC": frappe.db.get_value('Bank Account', 
						{'party_type': self.party_type,
						'party': self.party,
						'is_default': 1
						},'ifsc_code'),
				"AMOUNT": str(self.amount),
				"CURRENCY": currency,
				"TXNTYPE": self.transaction_type,
				"PAYEENAME": self.party,
				"REMARKS": 'Testing',
				"DEBITACC": integration_doc.account_number,
				"CREDITACC": frappe.db.get_value('Bank Account', 
						{'party_type': self.party_type,
						'party': self.party,
						'is_default': 1
						},'bank_account_no')
			}
			try:
				res = prov.initiate_transaction_without_otp(filters)
				if type(res) == str:
					self.status = 'Initiation Error'
					self.workflow_state = 'Initiation Error'
				else:
					if res['STATUS'] == 'SUCCESS':
						self.status = 'Initiated'
						self.workflow_state = 'Initiated'
					if res['STATUS'] == 'FAILURE':
						self.status = 'Initiation Failed'
						self.workflow_state = 'Initiation Failed'
			except:
				self.status = 'Initiation Error'
				self.workflow_state = 'Initiation Error'
				res = frappe.get_traceback()
			log_name = self.log_request('Initiate Transaction without OTP', filters, config, res)
			self.save()
			self.reload()
			if self.status in ['Initiation Error', 'Initiation Failed']:
				if not self.bobp:
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

@frappe.whitelist()
def update_transaction_status(obp_name=None,bobp_name=None):
	if obp_name:
		obp_list = {'name': obp_name}
	if bobp_name:
		obp_list = frappe.db.get_all('Outward Bank Payment', {'status': ['=', 'Initiated'], 'bobp': ['=', bobp_name]})

	for doc in obp_list:
		res = None
		obp_doc = frappe.get_doc('Outward Bank Payment', doc['name'])
		currency = frappe.db.get_value("Company", obp_doc.company, "default_currency")
		prov, config = obp_doc.get_api_provider_class()
		integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': obp_doc.company_bank_account})
		filters = {"UNIQUEID": obp_doc.name}
		try:
			res = prov.get_transaction_status(filters)
			if type(res) == str:
				obp_doc.status = 'Transaction Error'
				obp_doc.workflow_state = 'Transaction Error'
			else:
				if res['STATUS'] == 'SUCCESS':
					obp_doc.status = 'Transaction Completed'
					obp_doc.workflow_state = 'Transaction Completed'
				if res['STATUS'] in ['FAILURE', 'DUPLICATE']:
					obp_doc.status = 'Transaction Failed'
					obp_doc.workflow_state = 'Transaction Failed'
				if res['STATUS'] in ['PENDING', 'Pending For Processing']:
					obp_doc.status = 'Transaction Pending'
					obp_doc.workflow_state = 'Transaction Pending'
		except:
			obp_doc.status = 'Transaction Error'
			obp_doc.workflow_state = 'Transaction Error'
			res = frappe.get_traceback()
		
		log_name = obp_doc.log_request('Update Transaction Status', filters, config, res)
		obp_doc.save()
		obp_doc.reload()
		if obp_doc.status in ['Transaction Pending', 'Transaction Error', 'Transaction Failed']:
			if not obp_doc.bobp:
				frappe.throw(_(f'Kindly check request log for more info {log_name}'))

@frappe.whitelist()
def get_outstanding_reference_documents(args):

	if isinstance(args, string_types):
		args = json.loads(args)

	if args.get('party_type') == 'Member':
		return

	args['party_account'] =  frappe.db.get_value('Account', {'account_type': 'Payable','is_group': 0, 'company': args.get('company')})

	# confirm that Supplier is not blocked
	if args.get('party_type') == 'Supplier':
		supplier_status = get_supplier_block_status(args['party'])
		if supplier_status['on_hold']:
			if supplier_status['hold_type'] == 'All':
				return []
			elif supplier_status['hold_type'] == 'Payments':
				if not supplier_status['release_date'] or getdate(nowdate()) <= supplier_status['release_date']:
					return []

	party_account_currency = get_account_currency(args.get("party_account"))
	company_currency = frappe.get_cached_value('Company',  args.get("company"),  "default_currency")

	# Get negative outstanding sales /purchase invoices
	negative_outstanding_invoices = []
	if args.get("party_type") not in ["Student", "Employee"] and not args.get("voucher_no"):
		negative_outstanding_invoices = get_negative_outstanding_invoices(args.get("party_type"), args.get("party"),
			args.get("party_account"), args.get("company"), party_account_currency, company_currency)

	# Get positive outstanding sales /purchase invoices/ Fees
	condition = ""
	if args.get("voucher_type") and args.get("voucher_no"):
		condition = " and voucher_type={0} and voucher_no={1}"\
			.format(frappe.db.escape(args["voucher_type"]), frappe.db.escape(args["voucher_no"]))

	# Add cost center condition
	if args.get("cost_center"):
		condition += " and cost_center='%s'" % args.get("cost_center")

	date_fields_dict = {
		'posting_date': ['from_posting_date', 'to_posting_date'],
		'due_date': ['from_due_date', 'to_due_date']
	}

	for fieldname, date_fields in date_fields_dict.items():
		if args.get(date_fields[0]) and args.get(date_fields[1]):
			condition += " and {0} between '{1}' and '{2}'".format(fieldname,
				args.get(date_fields[0]), args.get(date_fields[1]))

	if args.get("company"):
		condition += " and company = {0}".format(frappe.db.escape(args.get("company")))

	outstanding_invoices = get_outstanding_invoices(args.get("party_type"), args.get("party"),
		args.get("party_account"), filters=args, condition=condition)

	for d in outstanding_invoices:
		d["exchange_rate"] = 1
		if party_account_currency != company_currency:
			if d.voucher_type in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
				d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
			elif d.voucher_type == "Journal Entry":
				d["exchange_rate"] = get_exchange_rate(
					party_account_currency,	company_currency, d.posting_date
				)
		if d.voucher_type in ("Purchase Invoice"):
			d["bill_no"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "bill_no")

	# Get all SO / PO which are not fully billed or aginst which full advance not paid
	orders_to_be_billed = []
	if (args.get("party_type") != "Student"):
		orders_to_be_billed =  get_orders_to_be_billed(args.get("posting_date"),args.get("party_type"),
			args.get("party"), args.get("company"), party_account_currency, company_currency, filters=args)

	data = negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed
	if not data:
		frappe.msgprint(_("No outstanding invoices found for the {0} {1} which qualify the filters you have specified.")
			.format(args.get("party_type").lower(), frappe.bold(args.get("party"))))

	return data