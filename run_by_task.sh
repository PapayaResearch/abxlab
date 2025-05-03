# Iterate filenames in conf/task. 
for file in conf/task/*.yaml; do
    echo ${file#conf/task/} | sed 's/\.yaml$//'
    python agent_lab_run.py task=${file#conf/task/}
done

