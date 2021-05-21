# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form
from frappe.model.mapper import get_mapped_doc

class BulkOutwardBankPayment(Document):
	def onload(self):
		self.set_onload('transaction_summary', self.get_transaction_summary())

	def get_transaction_summary(self):
		transaction_summary = [
						{'status':'Initiated','total_docs':0},
						{'status':'Initiation Error','total_docs':0},
						{'status':'Initiation Failed','total_docs':0},
						{'status':'Transaction Error','total_docs':0},
						{'status':'Transaction Failed','total_docs':0},
						{'status':'Transaction Pending','total_docs':0},
						{'status':'Transaction Completed','total_docs':0}]
		for row in transaction_summary:
			row['total_docs'] = frappe.db.count('Outward Bank Payment', {'bobp': self.name, 'workflow_state': row['status']})

		return transaction_summary
	def validate(self):
		total_payment_amount = 0
		for row in self.outward_bank_payment_details:
			total_payment_amount+=flt(row.amount)
		self.total_payment_amount = total_payment_amount
		self.no_of_payments = len(self.outward_bank_payment_details)

	def on_submit(self):
		if self.workflow_state == 'Approved':
			failed_obp_list = []
			integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': self.company_bank_account})

			password_defined = integration_doc.get_password(fieldname="transaction_password")
			password_entered = self.get_password(fieldname="transaction_password")

			if not password_defined == password_entered:
				frappe.throw(_(f'Invalid Password'))
				return
			for row in self.outward_bank_payment_details:
				data = {
				'party_type': row.party_type,
				'party': row.party,
				'amount': row.amount,
				'transaction_type': self.transaction_type,
				'company_bank_account': self.company_bank_account,
				'reconcile_action': self.reconcile_action,
				'transaction_password': password_entered,
				'bobp': self.name}
				if not frappe.db.exists('Outward Bank Payment', data):
					data['doctype'] = 'Outward Bank Payment'
					doc = frappe.get_doc(data)
					doc.save()
					doc.submit()
					status = frappe.db.get_value('Outward Bank Payment', doc.name, 'status')
					if status in  ['Initiation Error', 'Initiation Failed']:
						failed_obp_list.append(get_link_to_form("Outward Bank Payment", doc.name))
					frappe.db.set_value('Outward Bank Payment Details',{'parent':self.name,
						'party_type': row.party_type,
						'party': row.party,
						'amount': row.amount},'outward_bank_payment',doc.name)
					frappe.db.set_value('Outward Bank Payment Details',{'parent':self.name,
						'party_type': row.party_type,
						'party': row.party,
						'amount': row.amount,
						'outward_bank_payment':doc.name},'status', status)
			frappe.db.commit()
			self.reload()
			if failed_obp_list:
				failed_obp = ','.join(failed_obp_list)
				frappe.throw(_(f"Initiation failed for the below obp(s) {failed_obp}"))
			else:
				frappe.msgprint(_('Payment initiated successfully'))



@frappe.whitelist()
def fetch_failed_transaction(source_name, target_doc=None):
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
			"condition": lambda doc: doc.status not in ['Initiated', 'Transaction Completed']
		},
		}, target_doc)
	return doc