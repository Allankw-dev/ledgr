"""Making typed text safe for the formats we write it into.

A name, school or term a person typed is just text to us, but PDFs, CSV files and Excel sheets each read some
characters as instructions. Every document or export we generate passes user-supplied text through here.
"""

import re
from xml.sax.saxutils import escape  # nosec B406: only the escape() helper (output encoding); nothing is ever parsed

# Phone numbers ("+254 712 345 678", "(020) 555-1234") and negative amounts ("-500.00") legitimately start with
# + or -. They contain only digits and punctuation, so they can't call a spreadsheet function. Anything else
# that starts with + or - is treated as a possible formula.
_PLAIN_NUMBER = re.compile(r"^[+-]?\d[\d\s().,\-]*$")


def pdf_markup(value) -> str:
    """Text for a ReportLab Paragraph. Paragraph reads XML-like tags (<b>, <font>, <img src=...>), so a name
    containing "<" would crash the document, and an <img> tag would make the server fetch a URL of the
    typist's choosing while rendering. Escaping turns all of it back into the literal characters."""
    return "" if value is None else escape(str(value))


def csv_safe(value):
    """A cell starting with = + - @ (or a tab/return) runs as a formula when the file is opened in Excel or
    Sheets: =HYPERLINK(...) can send data to a stranger, older Excel even ran commands. A leading apostrophe
    makes spreadsheets show it as plain text. Non-text values (numbers, None) pass through untouched."""
    if not isinstance(value, str) or not value:
        return value
    first = value[0]
    if first in ("=", "@", "\t", "\r"):
        return "'" + value
    if first in ("+", "-") and not _PLAIN_NUMBER.match(value):
        return "'" + value
    return value


def xlsx_text(cell):
    """Keep a typed string in an .xlsx cell as TEXT. openpyxl stores any string starting with "=" as a formula,
    so call this on cells that hold user text (never on the intentional =D5-E5 / =SUM() formulas)."""
    if isinstance(cell.value, str) and cell.value[:1] == "=":
        cell.data_type = "s"
    return cell
