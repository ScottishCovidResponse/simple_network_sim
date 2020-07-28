# End-to-end run with the data pipeline

I've written some shell scripts to help me with this - they need some work. The run may not be reproducible as lots of changes are still in progress. The end-to-end run is a x stage process:

1. Upload data - I used `scripts/pipeline_upload.sh` to upload the data in `sample_input_files` to the current FTP server and register it with the SCRC data registry.
2. Download data - I used `scripts/pipeline_download.sh` with `test_pipeline/test_config.yaml` to download the same data back into `test_pipeline/test_download/`.
3. Run the model `python -m simple_network_sim.sampleUseOfModel -c test_pipeline/test_config.yaml` and visualise the results: `python -m simple_network_sim.network_of_populations.visualisation test_pipeline/access-*.yaml`. Check they are similar to a local run `python -m simple_network_sim.sampleUseOfModel`.
4. Upload the results 