# Copyright (c) 2025, Aerele and contributors
# For license information, please see license.txt

import frappe, json
from frappe import _
from six import string_types
from frappe.utils import flt
from frappe.model.document import Document
from frappe.core.page.background_jobs.background_jobs import get_info
from frappe.utils.background_jobs import enqueue

from bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration import initiate_transaction_without_otp

class SDBulkPayout(Document):
	def validate(self):
		total_payment_amount = 0
		for row in self.payouts:
			total_payment_amount+=flt(row.amount)
		self.total_payment_amount = total_payment_amount
		self.no_of_payments = len(self.payouts)
	
	def create_obp_records(self):
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
			frappe.msgprint(
				_("OBP record creation job added to queue. Please check after sometime.")
			)

def create_obp_records(doc):
	for row in doc.payouts:
		try:
			data = {
				'party_name': row.name1,
				'bank_account_no': row.account_number,
				'ifsc_code': row.ifsc_code,
				'amount': flt(row.amount),
				'remarks': row.remarks,
				'transaction_type': row.transaction_type,
				'company_bank_account': doc.company_bank_account,
				'reconcile_action': 'Skip Reconcile',
				'bulk_payout': doc.name,
				'bulk_payout_detail': row.name,
			}
			if not frappe.db.exists('Outward Bank Payment', data):
				data['doctype'] = 'Outward Bank Payment'
				obp_doc = frappe.get_doc(data)
				obp_doc.save(ignore_permissions=True)
				obp_doc.submit()
				status = frappe.db.get_value('Outward Bank Payment', obp_doc.name, 'workflow_state')
				frappe.db.set_value('SD Bulk Payout Details',{
					'parent': doc.name,
					'name': row.name,
				},'outward_bank_payment', obp_doc.name)
				initiate_transaction_without_otp(obp_doc.name)
			frappe.db.commit()
		except:
			error_message = frappe.get_traceback()+"\n\n BOBP Name: \n"+ doc.name
			frappe.log_error(error_message, "OBP Record Creation Error")
	frappe.db.set_value("SD Bulk Payout", doc.name, "workflow_state", "Initiated")

@frappe.whitelist()
def verify_and_initiate_transaction(payout_name, entered_password=None):
	if not payout_name or not entered_password:
		frappe.throw("Please send proper details")

	bulk_payout = frappe.get_doc("SD Bulk Payout", payout_name)

	if entered_password:
		integration_doc_name = frappe.get_value('Bank API Integration',{'bank_account': bulk_payout.company_bank_account},'name')
		defined_password = frappe.utils.password.get_decrypted_password('Bank API Integration', integration_doc_name, fieldname='transaction_password')
		if not entered_password == defined_password:
			frappe.throw(_("Invalid Password"))
		bulk_payout.create_obp_records()

