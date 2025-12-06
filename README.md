# paperless-ngx-document-follow-up
In paperless-ngx you can create a custom field with the type 'date'. But is does not yet allow to use a date value relative to the actual date for an Document filter or an view.
If your paperless-ngx installation is running as a docker pprojecct in some containers, this tool may help.
This files are allowing to create an additional container, which uses the paperless-ngx-API to set an document tag if the actual date is near the custom field date of your document.

## Usage:
- Create an custom field with data type "Date", e.g. with the name 'DueDate' or 'Deadline'.
- Assign it to some of your documents.
- Create or select a tag, e.g. with the name 'ToDo' or 'open'

Optional:
  - Filter your documents by that tag and save it as a view.
  - Activate the "Show on Dashboard" for that view

## How it's working:
  - Once per day (e.g. at 23:00 or 4:00, TARGET_HOUR) the script todo.py is scanning all your documents.
  - If the document has your 'DueDate' or 'Deadline' field and the date is e.g. less or equal to the actual date + e.g. 3 days (DAYS_AHEAD value), then the Tag is assigned to that document.
  So the document will appear in your view. After you have done the document, you can manually remove the tag from that document. Or optionally ...
  - If the date is less than actual date - e.g. 2 days (OVERDUE_UNSET_DAYS value) the tag is removed automatically.

## Installation:
- In paperless-ngx in the top right corner goto 'My Profile' of your account
- Use 'Regenerate' to create an 'API Auth Token' (if you don't have one yet) and save it somewhere.
- Create in your docker folder a new folder, e.g. paperless_overdue
- Copy the files from this repository to that folder
- Edit the .env file. Put in your values
- In the shell go to that folder and run
  docker compose build
  docker compose up
