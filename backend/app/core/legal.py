"""Legal constants shared by sign-up, the unsubscribe link and account deletion.

TERMS_VERSION is stored next to the time a person accepted the Terms and Privacy Policy. Change it whenever
either document changes in a way people should re-accept, and keep it equal to LEGAL_VERSION in
frontend/src/config/legal.ts.
"""

TERMS_VERSION = "2026-11-06"

# What a person is told, in the API's own words, when they try to create an account without agreeing.
TERMS_REQUIRED_MESSAGE = "Please accept the Terms of Service and Privacy Policy to create an account."
GUARDIAN_REQUIRED_MESSAGE = (
    "Please confirm you are 18 or older and the parent or legal guardian of the child you are signing up for."
)
