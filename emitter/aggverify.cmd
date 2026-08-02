@echo off
rem run de nuit : verification qcert-aggregate-1 par le verificateur de sol
set CH=C:\Users\U2380817\Downloads\corridor-research\claude-help
cd /d C:\Users\U2380817\Downloads\corridor-research\quoridor-frontier-research
python reference\qcert_aggregate_verify.py "%CH%\aggregate\aggregate.json" --artifact-root "%CH%\aggregate" --temp-dir "%CH%\work\aggverify_tmp" --progress-every 5000000 1> "%CH%\aggregate\AGGREGATE_VERIFY_RECEIPT.json" 2> "%CH%\replication\AGGVERIFY.err"
echo %ERRORLEVEL% > "%CH%\replication\AGGVERIFY.exitcode"
