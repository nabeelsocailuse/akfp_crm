// Copyright (c) 2025, nabeel saleem and contributors
// For license information, please see license.txt


frappe.ui.form.on("Tax Exemption Certificate", {
    donor: function (frm) {
      fetch_total_donation(frm);
    },
    fiscal_year: function (frm) {
      fetch_total_donation(frm);
    },
    date_of_issue: function(frm) {
      validate_date_of_issue(frm);
    },
  });
  
  function validate_date_of_issue(frm) {
    if (frm.doc.date_of_issue) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const issue_date = new Date(frm.doc.date_of_issue);
      issue_date.setHours(0, 0, 0, 0);
      
      if (issue_date > today) {
        frappe.msgprint({
          title: __('Invalid Date'),
          message: __('Date of Issue cannot be a future date. Please select today or a past date.'),
          indicator: 'orange'
        });
        frm.set_value('date_of_issue', '');
      }
    }
  }
  
  function fetch_total_donation(frm) {
    frm.set_value("total_donation", 0);
    if (frm.doc.donor && frm.doc.fiscal_year) {
      frappe.call({
        method: "akfp_crm.akfp_crm.doctype.tax_exemption_certificate.tax_exemption_certificate.get_total_donation",
        args: {
          donor: frm.doc.donor,
          fiscal_year: frm.doc.fiscal_year,
        },
        callback: function (r) {
          if (r.message) {
            frm.set_value("total_donation", r.message.total_donation || 0);
            if (r.message.message) {
              frappe.msgprint(r.message.message);
            }
          }
        },
      });
    }
  }
  
  
  
  
  