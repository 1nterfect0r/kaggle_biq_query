# API

Base URL: https://bigquery-competition-node-294682573887.europe-west1.run.app


## Top 10 vector search
Endpoint: /search?query=test
```json
[
  {
    "distance": 0.508790905454632,
    "question_summary": "Enable Now - Web Assistant: Test mode message editing for quizzes and general resources — how-to/configuration.\n",
    "url": "https://community.sap.com/t5/human-capital-management-q-a/how-to-edit-messages-in-test-mode-in-enable-now/qaq-p/12700067",
    "CENTROID_ID": 27
  },
  {
    "distance": 0.539837917096318,
    "question_summary": "Unknown - Unknown: Unknown feature — Unclear intent regarding an unspecified SAP product, module, and feature.\n",
    "url": "https://community.sap.com/t5/human-capital-management-q-a/sap/qaq-p/272262",
    "CENTROID_ID": 27
  },
  ...
]
```


## Cluster info
Endpoint: /cluster
```json
[
  {
    "label": "cpi/btp master data replication failure",
    "CENTROID_ID": 39,
    "count_of_records": 173
  },
  {
    "label": "ec time off post-approval notification error",
    "CENTROID_ID": 33,
    "count_of_records": 448
  },
  ...
]
```

## Monthly cluster share
Endpoint: /monthlyTimeSeries?year_begin=2022&year_end=2022
```json
[
  {
    "year": 2022,
    "month": 10,
    "CID_1": 0.0642857142857143,
    "CID_2": 0.00714285714285714,
    "CID_3": 0,
    ...
    "CID_45": 0
  },
  {
    "year": 2022,
    "month": 12,
    "CID_1": 0.0165289256198347,
    "CID_2": 0.0247933884297521,
    "CID_3": 0,
    ...
    "CID_45": 0
  },
  ...
]
```

## Get all Questions in a cluster
Endpoint: /questionsByCluster?centroid_id=2
```json
[
  {
    "question_summary": "Enable Now - Enable Now: Logged-on username personalization within test mode scoresheets using placeholders is explored, investigating the feasibility of displaying the user's name dynamically.\n",
    "url": "https://community.sap.com/t5/human-capital-management-q-a/capturing-logged-on-username-in-enable-now/qaq-p/14126697",
    "label": "enable now content display issue"
  },
  {
    "question_summary": "Unknown - Unknown: The display of a folder icon and numerical indicator requires adjustment, suggesting a how-to/configuration intent related to user interface customization.\n",
    "url": "https://community.sap.com/t5/human-capital-management-q-a/also-i-am-not-able-to-change-settings-it-showing-folder-and-1-how-to-remove/qaq-p/13788959",
    "label": "enable now content display issue"
  },
    ...
]
```

## Get min and max year
Endpoint: /yearRange
```json
[
  {
    "max_year": 2025,
    "min_year": 2005
  }
]
```
