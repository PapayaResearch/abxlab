mkdir -p tasks

# Download categories.csv
wget -O tasks/categories.csv "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=1365867936&format=csv"

# Download home.csv
wget -O tasks/home.csv "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=1198213948&format=csv"

# Download interventions.csv
wget -O tasks/interventions.csv "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=1925262691&format=csv"

# Download intents.csv
wget -O tasks/intents.csv "https://docs.google.com/spreadsheets/d/15LA25I-z8uz6UaF6tXZ9MEMkgbFvanUYTJqlbKdPnhI/export?gid=301715508&format=csv"
