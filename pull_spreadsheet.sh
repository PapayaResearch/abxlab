# Download intent.csv
wget --header "Authorization: Bearer ya29.a0AZYkNZg4Tc0Lhsl9Yq2ZlrTCnUvd3F7TItzDXSXLmI3oWmnkX3VGsgeXbsXcFAndyhMYePQ7szCsPLg2qMFOlZl2kWS_vBubuOkc82Wc11Vv9l43IcFaSfCr5cfppcUJXdjGj2ipa2Wf4tKCdjfsZFZOW8KFd-yZjdPCwefQaCgYKASQSARQSFQHGX2MiZ9WWRikDGDGqPDjNhN050Q0175" -o file "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=301715508&format=csv"

# Download intervention.csv
wget --header "Authorization: Bearer ya29.a0AZYkNZg4Tc0Lhsl9Yq2ZlrTCnUvd3F7TItzDXSXLmI3oWmnkX3VGsgeXbsXcFAndyhMYePQ7szCsPLg2qMFOlZl2kWS_vBubuOkc82Wc11Vv9l43IcFaSfCr5cfppcUJXdjGj2ipa2Wf4tKCdjfsZFZOW8KFd-yZjdPCwefQaCgYKASQSARQSFQHGX2MiZ9WWRikDGDGqPDjNhN050Q0175" -o file "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=1925262691&format=csv"

# Download product.csv
wget --header "Authorization: Bearer ya29.a0AZYkNZg4Tc0Lhsl9Yq2ZlrTCnUvd3F7TItzDXSXLmI3oWmnkX3VGsgeXbsXcFAndyhMYePQ7szCsPLg2qMFOlZl2kWS_vBubuOkc82Wc11Vv9l43IcFaSfCr5cfppcUJXdjGj2ipa2Wf4tKCdjfsZFZOW8KFd-yZjdPCwefQaCgYKASQSARQSFQHGX2MiZ9WWRikDGDGqPDjNhN050Q0175" -o file "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=745135561&format=csv"

# Rename files
mv "export?gid=301715508&format=csv" "intents.csv"
mv "export?gid=1925262691&format=csv" "interventions.csv"
mv "export?gid=745135561&format=csv" "products.csv"

# Replace files in /tasks
rm -rf /tasks/intents.csv
rm -rf /tasks/interventions.csv
rm -rf /tasks/products.csv

mv intents.csv tasks
mv interventions.csv tasks
mv products.csv tasks