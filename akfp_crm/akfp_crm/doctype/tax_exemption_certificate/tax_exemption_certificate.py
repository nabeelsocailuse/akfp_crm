# Copyright (c) 2025, nabeel saleem
# For license information, please see license.txt

import frappe
import base64
import qrcode
import io
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, getdate, nowdate
from frappe import _


class TaxExemptionCertificate(Document):
    def validate(self):
        self.validate_date_of_issue()
        self.make_donor_readonly()

    def validate_date_of_issue(self): ## date of issue should not be less then today 
        if not self.date_of_issue:
            return

        today = getdate(nowdate())
        issue_date = getdate(self.date_of_issue)

        if issue_date < today:
            frappe.throw(
                _("Date of Issue cannot be earlier than today."),
                title=_("Invalid Date")
            )


    def make_donor_readonly(self):
        if not self.is_new() and self.has_value_changed("donor"):
            frappe.throw(
                _("Donor field cannot be changed after creation."),
                title=_("Read-Only Field")
            )        


    def before_insert(self):
        if not self.certificate_number:
            current_year = now_datetime().year
            prefix = f"TEX-{current_year}-"

            last_cert = frappe.db.sql(
                """
                SELECT certificate_number 
                FROM `tabTax Exemption Certificate`
                WHERE certificate_number LIKE %s
                ORDER BY certificate_number DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
                as_dict=True,
            )

            last_number = (
                int(last_cert[0].certificate_number.split("-")[-1]) + 1
                if last_cert
                else 1
            )
            self.certificate_number = f"{prefix}{last_number:03d}"

        if not self.generated_timestamp:
            self.generated_timestamp = now_datetime()

    def get_qr_code(self):  ##generate qr code 
        url = get_url(f"/verify-certificate?name={self.name}")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@frappe.whitelist()
def get_total_donation(donor, fiscal_year=None):
    if not donor:
        return {"total_donation": 0, "message": _("Please select a donor first.")}
    if not fiscal_year:
        return {"total_donation": 0, "message": _("Please select a fiscal year.")}

    fy = frappe.db.get_value(
        "Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fy:
        return {"total_donation": 0, "message": _("Fiscal Year not found.")}

    # 🧮 Sum of all PAID donations (excluding pledge)
    paid_total = frappe.db.sql(
        """
        SELECT SUM(pd.donation_amount) AS total
        FROM `tabPayment Detail` pd
        INNER JOIN `tabDonation` dn ON dn.name = pd.parent
        WHERE pd.donor = %s
          AND dn.due_date BETWEEN %s AND %s
          AND dn.docstatus = 1
          AND dn.status IN ('Paid', 'Partly Paid', 'Overdue', 'Partly Return', 'Credit Note Issued')
          AND (dn.contribution_type IS NULL OR dn.contribution_type != 'Pledge')
        """,
        (donor, fy.year_start_date, fy.year_end_date),
        as_dict=True,
    )[0].total or 0

    # 💸 Sum of all RETURN donations
    returned_total = frappe.db.sql(
        """
        SELECT SUM(pd.donation_amount) AS total
        FROM `tabPayment Detail` pd
        INNER JOIN `tabDonation` dn ON dn.name = pd.parent
        WHERE pd.donor = %s
          AND dn.due_date BETWEEN %s AND %s
          AND dn.docstatus = 1
          AND dn.status = 'Return'
        """,
        (donor, fy.year_start_date, fy.year_end_date),
        as_dict=True,
    )[0].total or 0

    remaining_total = paid_total - returned_total

    if remaining_total <= 0:
        return {
            "total_donation": 0,
            "message": _("No valid donation amount found for donor '{0}' in fiscal year '{1}'.").format(
                donor, fiscal_year
            ),
        }

    return {"total_donation": remaining_total}




