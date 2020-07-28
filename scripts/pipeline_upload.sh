token=$1 #Data registry token
username=$2 #FTP username
password=$3 #FTP password
remoteuri='ssh://boydorr.gla.ac.uk/srv/ftp/scrc/'
remoteurioverride='ftp://boydorr.gla.ac.uk/scrc/'
namespace='simple_network_sim_test'
accessibility='0'

# This script is deliberately repetitious to allow future customization

cd .. #We're in the scripts/ folder

# Commutes
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/commutes/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/commutes/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/commutes' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Compartment Transition
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/compartment-transition/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/compartment-transition/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/compartment-transition-1' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/compartment-transition/2/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/compartment-transition/2/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/compartment-transition-2' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Full Mixing Matrix
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/full-mixing-matrix/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/full-mixing-matrix/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/full-mixing-matrix' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Infection Probability
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/infection-probability/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/infection-probability/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/infection-probability' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Infectious Compartments
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/infectious-compartments/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/infectious-compartments/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/infectious-compartments-1' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/infectious-compartments/2/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/infectious-compartments/2/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/infectious-compartments-2' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Initial Infections
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/initial-infections/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/initial-infections/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/initial-infections' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Locations (nb this is the only .json file)
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/locations/1/data.json' \
'--namespace' $namespace \
'--storage-location-path' 'human/locations/1/data.json' \
'--accessibility' $accessibility \
'--data-product-name' 'human/locations' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Mixing Matrix
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/mixing-matrix/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/mixing-matrix/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/mixing-matrix' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Movement Multipliers
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/mixing-matrix/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/mixing-matrix/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/mixing-matrix' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Population
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/population/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/population/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/population' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Random Seed
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/random-seed/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/random-seed/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/random-seed' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Start-End Dates
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/start-end-date/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/start-end-date/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/start-end-date' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Stochasic Mode
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/stochastic-mode/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/stochastic-mode/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/stochastic-mode' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password

# Trials
python -m data_pipeline_api.registry.upload_data_product \
'--data-product-path' 'sample_input_files/human/trials/1/data.h5' \
'--namespace' $namespace \
'--storage-location-path' 'human/trials/1/data.h5' \
'--accessibility' $accessibility \
'--data-product-name' 'human/trials' \
'--data-product-version' '0.1.0' \
'--token' $token \
'--remote-uri' $remoteuri \
'--remote-uri-override' $remoteurioverride \
'--remote-option' 'username' $username \
'--remote-option' 'password' $password