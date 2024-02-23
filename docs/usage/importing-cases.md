# Importing Cases

The web filebrowser allows you to import cases that are already available on the server. It supports cases that are stored in individual folders, e.g.: 

```
.
├── case_1/
│   ├── reco.000.000.dcm
│   ├── reco.000.001.dcm
|   ...
│   └── reco.038.175.dcm
├── case_2/
├── case_3/
└── case_4/
```

The "import folder" button will become available on folders that have no subfolders. 

<div class="grid" style="grid-template-columns: 1fr 1fr 1fr" markdown>

![screenshot](site:images/import_case/import_case_1.png)

![screenshot](site:images/import_case/import_case_2.png)

![screenshot](site:images/import_case/import_case_3.png)

</div>

GRAVIS will fill in the patient name, mrn, and accession number from the DICOMs if it can find them. You must select which processing type to use for the case. 

![screenshot](site:images/import_case/import_case_4.png)
