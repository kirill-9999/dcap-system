// webui/static/js/app.js

function showCreateTaskModal() {
    document.getElementById('create-task-modal').style.display = 'flex';
}

function closeCreateTaskModal() {
    document.getElementById('create-task-modal').style.display = 'none';
}

async function createTask() {
    const path = document.getElementById('task-path').value.trim();
    if (!path) {
        alert('⚠️ Укажите путь к папке');
        return;
    }
    
    const extensions = document.getElementById('task-extensions').value.trim();
    const maxSize = parseInt(document.getElementById('task-max-size').value) || 50;
    const recursive = document.getElementById('task-recursive').checked;
    
    const data = {
        resource_path: path,
        resource_type: 'FILESYSTEM',
        extensions: extensions,
        max_file_size_mb: maxSize,
        recursive: recursive
    };
    
    try {
        const response = await fetch('/api/tasks/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Задание создано!\nID: ${result.task_id}\nПуть: ${result.resource_path}`);
            closeCreateTaskModal();
            loadTasks(); // Обновляем список
        } else {
            alert(`❌ Ошибка: ${result.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert(`❌ Ошибка: ${error.message}`);
    }
}

// Закрытие модального окна по клику вне его
document.addEventListener('click', function(e) {
    const modal = document.getElementById('create-task-modal');
    if (e.target === modal) {
        closeCreateTaskModal();
    }
});