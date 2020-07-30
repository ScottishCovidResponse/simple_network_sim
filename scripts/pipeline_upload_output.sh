token=$1
access=$2
username=$3
password=$4

cd ..

python -m data_pipeline_api.registry.access_upload \
'--model-config' 'test_pipeline/test_config.yaml' \
'--config' $access \
'--remote-uri' 'ssh://boydorr.gla.ac.uk/srv/ftp/scrc/' \
'--remote-uri-override' 'ftp://boydorr.gla.ac.uk/scrc/' \
'--submission-script' 'scripts/pipeline_submission.sh' \
'--token' $token \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password