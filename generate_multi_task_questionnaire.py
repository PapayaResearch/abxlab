import os
import webbrowser

def generate_multi_task_questionnaire():
    # Define the experiment directory
    root_dir = "."
    human_obs_dir = os.path.join(root_dir, "human_observation")
    
    if not os.path.isdir(human_obs_dir):
        print(f"Error: '{human_obs_dir}' directory not found!")
        return
    
    # Find all exp* directories
    exp_dirs = [d for d in os.listdir(human_obs_dir) 
               if os.path.isdir(os.path.join(human_obs_dir, d)) and d.startswith('exp')]
    exp_dirs.sort(key=lambda x: (len(x), x))  # Sort by length first, then alphabetically
    
    if not exp_dirs:
        print("No experiment directories found!")
        return
    
    # Generate HTML for each task
    tasks_html = ""
    for i, exp_name in enumerate(exp_dirs):
        exp_path = os.path.join(human_obs_dir, exp_name)
        
        # Find subdirectories (options) in this experiment
        options = [d for d in os.listdir(exp_path) 
                  if os.path.isdir(os.path.join(exp_path, d))]
        
        if len(options) == 0:
            print(f"Skipping {exp_name}: No options found")
            continue
        
        # Generate HTML for this task's options
        options_html = ""
        
        # Special handling for single-option tasks
        if len(options) == 1:
            option = options[0]
            option_path = os.path.join(exp_path, option)
            
            # Find screenshot image
            images = []
            for root, _, files in os.walk(option_path):
                for file in files:
                    if file.endswith('.png') and "screenshot" in file.lower():
                        images.append(os.path.join(root, file))
            
            if not images:
                # If no screenshot, find any PNG
                for root, _, files in os.walk(option_path):
                    for file in files:
                        if file.endswith('.png'):
                            images.append(os.path.join(root, file))
            
            if images:
                image_path = images[0]  # Use the first image found
                rel_path = os.path.relpath(image_path, start=root_dir)
                image_url = rel_path.replace("\\", "/")
                
                # Create a more readable display name
                display_name = option.replace("-", " ").title()
                
                options_html += f"""
            <div class="single-option">
                <div class="image-container">
                    <img src="{image_url}" alt="{display_name}">
                    <div class="option-label">{display_name}</div>
                </div>
                <div class="choice-question">
                    <p>Would you purchase this product?</p>
                    <label class="radio-option">
                        <input type="radio" name="{exp_name}" value="yes_{option}" required>
                        <span>Yes</span>
                    </label>
                    <label class="radio-option">
                        <input type="radio" name="{exp_name}" value="no_{option}" required>
                        <span>No</span>
                    </label>
                </div>
            </div>
"""
                
        else:
            # Multiple options - proceed as before
            for option in options:
                option_path = os.path.join(exp_path, option)
                
                # Find screenshot image
                images = []
                for root, _, files in os.walk(option_path):
                    for file in files:
                        if file.endswith('.png') and "screenshot" in file.lower():
                            images.append(os.path.join(root, file))
                
                if not images:
                    # If no screenshot, find any PNG
                    for root, _, files in os.walk(option_path):
                        for file in files:
                            if file.endswith('.png'):
                                images.append(os.path.join(root, file))
                
                if images:
                    image_path = images[0]  # Use the first image found
                    rel_path = os.path.relpath(image_path, start=root_dir)
                    image_url = rel_path.replace("\\", "/")
                    
                    # Create a more readable display name
                    display_name = option.replace("-", " ").title()
                    
                    options_html += f"""
            <label class="option">
                <input type="radio" name="{exp_name}" value="{option}" required>
                <img src="{image_url}" alt="{display_name}">
                <div class="option-label">{display_name}</div>
            </label>
"""
        
        # Create task div with navigation buttons
        task_html = f"""
        <div class="task" id="task-{exp_name}" style="display: none;">
            <h2>Task {i+1}: {exp_name}</h2>
            <p class="task-description">{
                "Please select your preferred option:" if len(options) > 1 
                else "Please review this product:"
            }</p>
            {options_html}
            <div class="navigation">
                {"<button type='button' class='prev-button' onclick='prevTask()'>Previous Task</button>" if i > 0 else ""}
                {"<button type='button' class='next-button' onclick='nextTask()'>Next Task</button>" if i < len(exp_dirs)-1 else "<button type='button' class='submit-button' onclick='submitForm()'>Submit All Responses</button>"}
            </div>
        </div>
        """
        tasks_html += task_html
    
    # Create the complete HTML
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Product Preference Questionnaire</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
        .task { margin-bottom: 40px; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .option { display: block; margin: 30px 0; vertical-align: top; text-align: center; width: 100%; }
        .option img { width: 100%; height: auto; display: block; border: 1px solid #eee; margin-top: 10px; }
        .single-option { margin: 30px 0; text-align: center; }
        .image-container { width: 100%; }
        .image-container img { width: 100%; height: auto; display: block; border: 1px solid #eee; margin-bottom: 15px; }
        .choice-question { margin-top: 20px; background-color: #f9f9f9; padding: 15px; border-radius: 5px; }
        .radio-option { display: inline-block; margin: 0 20px; font-size: 1.1em; }
        .radio-option input { margin-right: 5px; transform: scale(1.2); }
        .option-label { margin-top: 15px; font-size: 1em; color: #555; }
        h1, h2 { color: #333; }
        button { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; 
                 border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 20px; margin-right: 10px; }
        button:hover { background-color: #45a049; }
        .submit-button { background-color: #2196F3; }
        .submit-button:hover { background-color: #0b7dda; }
        .task-description { margin-bottom: 15px; color: #555; }
        .navigation { margin-top: 30px; display: flex; justify-content: space-between; }
        .progress { margin-bottom: 20px; color: #666; font-size: 0.9em; }
        #progress-indicator { font-weight: bold; }
    </style>
</head>
<body>
    <h1>Product Preference Questionnaire</h1>
    <p>For each task, please select the option that you prefer.</p>
    
    <div class="progress">
        Task progress: <span id="progress-indicator">1</span> of <span id="total-tasks">TOTAL_TASKS</span>
    </div>
    
    <form id="questionnaire">
        TASKS_HTML
    </form>

    <script>
    // Navigation functions
    let currentTaskIndex = 0;
    const tasks = document.querySelectorAll('.task');
    const totalTasks = tasks.length;
    document.getElementById('total-tasks').textContent = totalTasks;
    
    function showTask(index) {
        // Hide all tasks
        tasks.forEach(task => task.style.display = 'none');
        
        // Show the current task
        tasks[index].style.display = 'block';
        
        // Update progress indicator
        document.getElementById('progress-indicator').textContent = index + 1;
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
    
    function nextTask() {
        // Check if current task has a selection
        const currentTaskId = tasks[currentTaskIndex].id;
        const taskName = currentTaskId.split('-')[1];
        const selected = document.querySelector(`input[name="${taskName}"]:checked`);
        
        if (!selected) {
            alert('Please make a selection before proceeding to the next task');
            return;
        }
        
        if (currentTaskIndex < totalTasks - 1) {
            currentTaskIndex++;
            showTask(currentTaskIndex);
        }
    }
    
    function prevTask() {
        if (currentTaskIndex > 0) {
            currentTaskIndex--;
            showTask(currentTaskIndex);
        }
    }
    
    function submitForm() {
        // Check if all required radio buttons are selected
        const radioGroups = document.querySelectorAll('input[type="radio"][required]');
        const groupNames = new Set();
        radioGroups.forEach(radio => groupNames.add(radio.name));
        
        let allSelected = true;
        let firstMissing = null;
        
        for (const name of groupNames) {
            if (!document.querySelector(`input[name="${name}"]:checked`)) {
                allSelected = false;
                if (!firstMissing) firstMissing = name;
            }
        }
        
        if (!allSelected) {
            alert(`Please make a selection for ${firstMissing}`);
            
            // Find and show the task with the missing selection
            for (let i = 0; i < tasks.length; i++) {
                if (tasks[i].id === `task-${firstMissing}`) {
                    currentTaskIndex = i;
                    showTask(currentTaskIndex);
                    break;
                }
            }
            
            return;
        }
        
        // Collect all responses
        const data = {};
        for (const name of groupNames) {
            const selected = document.querySelector(`input[name="${name}"]:checked`);
            data[name] = selected.value;
        }
        
        // Save responses
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'questionnaire_responses.json';
        a.click();
        
        alert('Thank you for completing the questionnaire!');
    }
    
    // Initialize the first task
    showTask(currentTaskIndex);
    </script>
</body>
</html>"""

    # Replace placeholders
    html = html.replace("TASKS_HTML", tasks_html)
    html = html.replace("TOTAL_TASKS", str(len(exp_dirs)))
    
    # Write the HTML to a file
    output_file = "multi_task_questionnaire.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Questionnaire generated: {output_file}")
    webbrowser.open(output_file)

if __name__ == "__main__":
    generate_multi_task_questionnaire() 