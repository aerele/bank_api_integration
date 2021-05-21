// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt
{% include 'bank_api_integration/bank_api_integration/utils/common_fields.js' %};
frappe.ui.form.on("Bulk Outward Bank Payment", {
		onload: function(frm){
			if(frappe.user.has_role("Bank Checker")){ 
				frm.set_df_property('transaction_password', 'hidden', 0);
				frm.toggle_reqd("transaction_password", true);
			} 
			else{
				frm.set_df_property('transaction_password', 'hidden', 1);
				frm.toggle_reqd("transaction_password", false);
			}
			frm.refresh_fields("transaction_password");
		},
		refresh: function(frm) {
			frm.trigger("show_summary");
			if (frm.doc.docstatus == 1 && frm.doc.status != 'Rejected'){ 
				frm.add_custom_button(__("Update Transaction Status"), function() {
				 frm.trigger('update_txn_status');
			 	});
				frm.add_custom_button(__("Recreate Failed Transactions"), function() {
					frm.trigger('recreate_failed_txn');
					 });
			}
		},
		recreate_failed_txn: function(){
			frappe.model.open_mapped_doc({
				method: "bank_api_integration.bank_api_integration.doctype.bulk_outward_bank_payment.bulk_outward_bank_payment.fetch_failed_transaction",
				frm: cur_frm,
				freeze_message: __("Fetching ...")
			})
		},
		update_txn_status: function(frm){
			frappe.call({
				method: "bank_api_integration.bank_api_integration.doctype.outward_bank_payment.outward_bank_payment.update_transaction_status",
				freeze: true,
				args: {bobp_name:frm.doc.name}
			})
		},
		after_workflow_action: (frm) => {
		if(frm.doc.workflow_state == "Rejected"){
		frm.set_value("status", "Pending");
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Reason for Rejection'),
			fields: [
				{
					"fieldname": "reason_for_rejection",
					"fieldtype": "Data",
					"reqd": 1,
				}
			],
			primary_action: function() {
				var data = d.get_values();
				frappe.call({
					method: "frappe.desk.form.utils.add_comment",
					args: {
						reference_doctype: me.frm.doctype,
						reference_name: me.frm.docname,
						content: __('Reason for Rejection: ')+data.reason_for_rejection,
						comment_email: frappe.session.user,
						comment_by: frappe.session.user_fullname
					},
					callback: function(r) {
						if(!r.exc) {
							frm.set_value("status", "Rejected");
							frm.save('Update');
							d.hide();
						}
					}
				});
			}
		});
		d.show();

		}
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