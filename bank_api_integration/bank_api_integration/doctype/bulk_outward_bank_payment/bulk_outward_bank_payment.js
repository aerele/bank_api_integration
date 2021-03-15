// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Outward Bank Payment", {
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
	}
}
);