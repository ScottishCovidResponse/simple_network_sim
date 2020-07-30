token=$1
config=$2

cd .. #We're in the scripts/ folder

python -m data_pipeline_api.registry.download --config $config --token $token