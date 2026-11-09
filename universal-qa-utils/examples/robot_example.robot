*** Settings ***
Library    Process
Library    universal_utils.robot.ReconciliationLibrary
Suite Setup    Create Synthetic Workbooks

*** Variables ***
${PYTHON}    python3
${SOURCE_A}    ${CURDIR}/demo-output/CAM.xlsx
${SOURCE_B}    ${CURDIR}/demo-output/MDG.xlsx
${FIELD_MAPPING}    {"PCID Name": "Name", "PCID Description": "Program Description", "Status Code": "Status Description"}
${VALUE_MAPPINGS}    {"Status Code": {"S0011": "Abandoned", "S0023": "Approved"}}

*** Test Cases ***
Config File Comparison Passes
    ${result}=    Compare Excel Files    config=${CURDIR}/config/cam_mdg.json
    Verify Reconciliation Passed    ${result}
    ${summary}=    Get Reconciliation Summary
    Should Be Equal As Integers    ${summary}[matched]    2
    Should Be Equal As Integers    ${summary}[exceptions]    0

Inline JSON Mapping Comparison Passes
    Compare Excel Files
    ...    ${SOURCE_A}
    ...    ${SOURCE_B}
    ...    sheet_a=CAM
    ...    sheet_b=MDG
    ...    key_a=PCID
    ...    key_b=ID
    ...    field_mapping=${FIELD_MAPPING}
    ...    value_mappings=${VALUE_MAPPINGS}
    Verify Reconciliation Passed
    ${summary}=    Get Reconciliation Summary
    Should Be Equal    ${summary}[passed]    ${True}

*** Keywords ***
Create Synthetic Workbooks
    ${created}=    Run Process    ${PYTHON}    ${CURDIR}/cam_mdg_example.py    --write-only
    Should Be Equal As Integers    ${created.rc}    0
