// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt
{% include 'bank_api_integration/bank_api_integration/utils/common_fields.js' %};
frappe.ui.form.on("Bulk Outward Bank Payment", {
		refresh: function(frm) {
			frm.trigger("show_summary");
			if (frm.doc.docstatus == 1 && frm.doc.workflow_state != 'Rejected'){
				if(frm.doc.__onload.initiated_txn_count ){
				frm.add_custom_button(__("Update Transaction Status"), function() {
				 frm.trigger('update_txn_status');
			 	});
				}
				if(frm.doc.__onload.failed_doc_count){
				frm.add_custom_button(__("Recreate Failed Transactions"), function() {
					frm.trigger('recreate_failed_txn');
					 });
					}
			}
			if(frm.doc.docstatus == 0 && frappe.user.has_role('Bank Checker') && !frm.doc.__islocal){
				frm.add_custom_button(__("Approve"), function(){
				   let bank_account = frm.doc.company_bank_account;
				   frappe.call({
					   method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_field_status',
					   freeze: true,
					   args: {
						   'bank_account': bank_account
					   },
					   callback: function(r) {
						   let data = r.message;
						   if (data) {
							   let d = new frappe.ui.Dialog({
								   title: __('Enter the Details'),
								   fields: [
									   {
										   fieldtype: "Data",
										   label: __("Transaction Password"),
										   fieldname: "transaction_password",
										   reqd: 1,
										   depends_on: `eval: ${data.is_pwd_security_enabled}`
									   },
									   {
										   fieldtype: "Int",
										   label: __("OTP"),
										   fieldname: "otp",
										   reqd: 1,
										   depends_on: `eval: ${data.is_otp_enabled}`
									   }
								   ],
								   primary_action: function() {
									var data = d.get_values();
									frappe.call({
										method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.verify_transaction",
										freeze: true,
										args: {
											doctype: "Bulk Outward Bank Payment",
											docname: frm.doc.name,
											entered_password:data.transaction_password,
											otp: data.otp
										},
									callback: function(r) {
										if(!r.exc) {
										d.hide();
										frm.reload_doc();
										}
									}
								}
									)
								   }
							   });
							   d.show();
						   }
					   }
				   });
			   }).addClass("btn-primary");		
			   frm.add_custom_button(__("Reject"), function(){
				   var reject_dialog = new frappe.ui.Dialog({
						   title: __('Reason for Rejection'),
						   fields: [
							   {
								   "fieldname": "reason",
								   "fieldtype": "Small Text",
								   "reqd": 1,
								   "label": "Reason"
							   }
						   ],
						   primary_action: function() {
							   var data = reject_dialog.get_values();
							   frappe.call({
								   method: "frappe.desk.form.utils.add_comment",
								   freeze: true,
								   args: {
									   reference_doctype: me.frm.doctype,
									   reference_name: me.frm.docname,
									   content: __('Reason for Rejection: ') + data.reason,
									   comment_email: frappe.session.user,
									   comment_by: frappe.session.user_fullname
								   },
								   callback: function(r) {
									if(!r.exc) {
										frappe.call({
											method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.update_status",
											freeze: true,
											args: {
												doctype_name: "Bulk Outward Bank Payment",
												docname: frm.doc.name,
												status: "Rejected"
											},
										callback: function(r) {
											if(!r.exc) {
											reject_dialog.hide();
											frm.reload_doc();
											}
										}
									}
										)
									}
								   }
							   });
						   }
					   });
					   reject_dialog.show();
			   }).addClass("btn-danger");
		   }
		},
		company_bank_account: function(frm) {
			frappe.call({
				method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_transaction_type',
				args: {
					"bank_account":frm.doc.company_bank_account
				},
				callback: function(r) {
					if (r.message) {
						frm.set_df_property("transaction_type","options",r.message.join('\n'))
					}
				}
			});
		},
		recreate_failed_txn: function(){
			frappe.model.open_mapped_doc({
				method: "bank_api_integration.bank_api_integration.doctype.bulk_outward_bank_payment.bulk_outward_bank_payment.recreate_failed_transaction",
				frm: cur_frm,
				freeze_message: __("Fetching ...")
			})
		},
		update_txn_status: function(frm){
			frappe.call({
				method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.update_transaction_status",
				freeze: true,
				freeze_message: __("Processing..."),
				args: {bobp_name:frm.doc.name}
			})
		},
	show_summary: function(frm) {
		let transaction_summary = frm.doc.__onload.transaction_summary;
		if(frm.doc.workflow_state != 'Pending' && frm.doc.workflow_state != 'Rejected') {
			let section = frm.dashboard.add_section(
				frappe.render_template('bulk_outward_bank_payment', {
					data: transaction_summary
				})
			);
			frm.dashboard.show();
		}
	}
}
);