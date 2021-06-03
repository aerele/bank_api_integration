# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.model.mapper import get_mapped_doc
from frappe.core.page.background_jobs.background_jobs import get_info
from frappe.utils.background_jobs import enqueue
from bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration import *
class BulkOutwardBankPayment(Document):
	def on_update(self):
		is_authorized(self)
	def onload(self):
		self.set_onload('transaction_summary', self.get_transaction_summary())

	def get_transaction_summary(self):
		failed_doc_count = 0
		initiated_txn_count = 0
		transaction_summary = [
						{'status':'Initiated','total_docs':0},
						{'status':'Initiation Pending','total_docs':0},
						{'status':'Initiation Error','total_docs':0},
						{'status':'Initiation Failed','total_docs':0},
						{'status':'Transaction Error','total_docs':0},
						{'status':'Transaction Failed','total_docs':0},
						{'status':'Transaction Pending','total_docs':0},
						{'status':'Transaction Completed','total_docs':0}]
		for row in transaction_summary:
			row['total_docs'] = frappe.db.count('Outward Bank Payment', {'bobp': self.name, 'workflow_state': row['status']})
			if row['status'] in ['Initiation Error',
								'Initiation Failed',
								'Transaction Error',
								'Transaction Failed'] and row['total_docs']:
				failed_doc_count += row['total_docs']
			
			if row['status'] in ['Initiated', 'Initiation Pending', 'Transaction Pending'] and row['total_docs']:
				initiated_txn_count += row['total_docs']

		self.set_onload('failed_doc_count', failed_doc_count)
		self.set_onload('initiated_txn_count', initiated_txn_count)
		return transaction_summary
	def validate(self):
		total_payment_amount = 0
		for row in self.outward_bank_payment_details:
			row.remarks = self.remarks
			total_payment_amount+=flt(row.amount)
		self.total_payment_amount = total_payment_amount
		self.no_of_payments = len(self.outward_bank_payment_details)

	def bulk_create_obp_records(self):
		enqueued_jobs = [d.get("job_name") for d in get_info()]
		if self.name in enqueued_jobs:
			frappe.throw(
				_("OBP record creation already in progress. Please wait for sometime.")
			)
		else:
			enqueue(
				create_obp_records,
				queue="default",
				timeout=6000,
				event="obp_record_creation",
				job_name=self.name,
				doc = self
			)
			frappe.throw(
				_("OBP record creation job added to queue. Please check after sometime.")
			)

def create_obp_records(doc):
	for row in doc.outward_bank_payment_details:
		row = vars(row)
		if row['idx'] == 0:
			continue
		try:
			data = {
			'party_type': row['party_type'],
			'party': row['party'],
			'amount': row['amount'],
			'remarks': doc.remarks,
			'transaction_type': doc.transaction_type,
			'company_bank_account': doc.company_bank_account,
			'reconcile_action': doc.reconcile_action,
			'bobp': doc.name}
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
				initiate_transaction_without_otp(obp_doc.name)
			frappe.db.commit()
		except:
			error_message = frappe.get_traceback()+"\n\n BOBP Name: \n"+ doc.name
			frappe.log_error(error_message, "OBP Record Creation Error")

@frappe.whitelist()
def recreate_failed_transaction(source_name, target_doc=None):
	doc = get_mapped_doc("Bulk Outward Bank Payment", source_name,	{
		"Bulk Outward Bank Payment": {
			"doctype": "Bulk Outward Bank Payment",
			"field_map": {
				"company": "company",
				"company_bank_account": "company_bank_account",
				"reconcile_action": "reconcile_action",
				"transaction_type": "transaction_type"
			}
			},
		"Outward Bank Payment Details":{
			"doctype": "Outward Bank Payment Details",
			"field_map": {
				"party_type": "party_type",
				"party": "party",
				"amount": "amount"
			},
			"condition": lambda doc: doc.status not in ['Initiated', 'Transaction Completed', 'Initiation Pending', 'Transaction Pending']
		},
		}, target_doc)
	return doc