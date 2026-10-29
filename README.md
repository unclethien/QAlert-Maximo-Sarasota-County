# Sarasota County MAS AI Pilot: sample dataset

This project holds a **fake but realistic** sample dataset for the Sarasota County MAS AI Pilot. It shows how service requests from QAlert arrive in Maximo, and what the AI should notice about each one:

- **Missing information:** for example, no house number, a wrong address, or the wrong request type.
- **Duplicates:** several requests about the same problem.
- **Past or planned work:** earlier repairs or upcoming projects at the same place.

Every name, phone number, email, and street in this dataset is made up. None of it comes from real County records.

> **Please note:** this dataset is built on our team's assumptions about how QAlert and Maximo work at Sarasota County. It still needs to be checked. If something doesn't match how things really work, please tell us (see [Give feedback](#give-feedback)).

## How to look around

You don't need a GitHub account to view this project. GitHub works like a shared folder on the web:

- Click a folder to open it.
- Click a file to view it.
- Use your browser's Back button to go back.

## What's in each folder

| Folder or file | What's inside |
|---|---|
| [`docs/sample-dataset.md`](docs/sample-dataset.md) | **Start here.** A plain-language guide to the whole dataset. |
| [`data/answer-key.csv`](data/answer-key.csv) | **The most useful file.** One row per service request: what the AI should flag, who to contact, and what to ask. |
| [`data/maximo/`](data/maximo) | The fake Maximo records: service requests (`sr.csv`), work orders (`wo.csv`), work logs (`worklog.csv`), and people (`person.csv`). |
| [`data/qalert/`](data/qalert) | The fake QAlert records, including the staff list (`employees.json`) used to look up who entered a request. |
| [`data/reference/`](data/reference) | A stand-in for the County's address list. |
| [`scripts/`](scripts) | The programs that create the data. You can ignore this folder. |

## Reading the data

- **`.csv` files** show as a table in your browser. Use the search box above the table to find a request, for example `SR800012`.
- **`.json` files** show as text. The guide in [`docs/sample-dataset.md`](docs/sample-dataset.md) explains what they contain.

## Downloading files to open in Excel

- **One file:** open it, then click the **download icon** (an arrow pointing down) at the top right of the file view.
- **Everything:** on this page, click the green **Code** button, then **Download ZIP**. Unzip the file and open any `.csv` file in Excel.

## Give feedback

When something looks wrong or doesn't match how things really work, send Thien Nguyen:

1. the file name, for example `answer-key.csv`;
2. the request number, for example `SR800012`;
3. what you'd expect it to say instead.

## For developers

The dataset is created by a Python script with no extra packages. Running it again always produces the same files.

```bash
python3 scripts/generate_pilot_dataset.py   # rebuilds everything under data/
python3 scripts/validate_pilot_dataset.py   # checks the files; exits 1 if any check fails
```

To change the data, edit `scripts/pilot_catalog.py` and run both commands again. The fields, scenarios, and assumptions are described in [`docs/sample-dataset.md`](docs/sample-dataset.md).
