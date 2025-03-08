from flask import Flask, request, render_template, jsonify
import requests
import os
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

MONGO_URI = os.getenv("MONGO_URI") 

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.tasks_db 
user_tasks_weekly_collection = db.user_tasks_weekly
weekly_task_messages_collection = db.weekly_task_messages

date_time_today = datetime.datetime.now()
date_today = datetime.date(
    date_time_today.year,
    date_time_today.month,
    date_time_today.day
)
start_of_week = date_today - datetime.timedelta(days=date_today.weekday())

# Serve the form page
@app.route('/form')
def form():
    user_id = request.args.get('user_id') 
    return render_template('weekly.html', user_id=user_id)

def send_tasks_to_db(user_id, tasks):
    for task in tasks:
        task_data = {
            "user_id": user_id,
            "week_start": start_of_week.strftime("%d-%m-%Y (%A)"),
            "task_name": task['taskName'],
            "why": task['taskWhy'],
            "how": task["taskHow"],
            "dependencies": task["Dependencies"],
            "estimated_time": f"{task['estimatedTime']['value']} {task['estimatedTime']['unit']}\n",
            "great_performance": task["greatPerformance"],
            "good_performance": task["goodPerformance"],
            "bad_performance": task["badPerformance"],
            "completed": False
        }
        user_tasks_weekly_collection.insert_one(task_data)

def send_tasks_to_discord(user_id, tasks):
    map_users = {
        "Manoj": 1169217682307043508,
        "Prashanth": 1169252470996869121,
        "Sandesh": 1185194615125577842,
        "Vivek": 1274011740761489440,
        "Akshitha": 1098204173922742305,
        "Adi": 1171425439076581379,
        "Pavithra": 1164823101524152380,
        "Saranya": 1168908845398118450,
        "Sharon": 1095989346022207508
    }

    webhook_url = f"{os.getenv("WEBHOOK_WEEKLY")}?wait=true"

    embeds = []
    fields = []

    for i, task in enumerate(tasks, 0):
        fields.append({
                "name": f"📌 **Task {i+1}: {task['taskName']}** ",
                "value":f"────────────\n"
                        f"📖 **Why?:**\n{task['taskWhy']}\n"
                        f"────────────\n"
                        f"🔍 **How?:**\n{task['taskHow']}\n"
                        f"────────────\n"
                        f"**Dependencies:**\n<@{map_users[task['Dependencies']]}>\n"
                        f"────────────\n"
                        f"⏳ **Estimated Time:**\n{task['estimatedTime']['value']} {task['estimatedTime']['unit']}\n"
                        f"────────────\n"
                        f"**Great performance:**\n{task['greatPerformance']}\n"
                        f"\n"
                        f"**Good performance:**\n{task['goodPerformance']}\n"
                        f"\n"
                        f"**Bad performance:**\n{task['badPerformance']}\n"
                        f"────────────\n",
            })
        
    embeds.append(
            {
                "title": f"📅 Tasks for the week starting:\n{start_of_week.strftime("%d-%m-%Y (%A)")}",
                "description": f"📝 **Tasks added by <@{user_id}>**",
                "inline": False,
                "fields": fields,
                "color": 0x0059FF,
            }
        )

    payload = {
        "embeds": embeds
    }

    response = requests.post(webhook_url, json=payload)

    if response.status_code == 200:
        message_data = response.json()  
        message_id = message_data.get("id")
        print("Message ID:", message_id)

        message_details = {
            "user_id": user_id, 
            "week_start": start_of_week.strftime("%d-%m-%Y (%A)"), 
            "task_messages": message_id
        }
        weekly_task_messages_collection.insert_one(message_details)

    else:
        print("Failed to send message:", response.text)

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "Invalid or missing JSON data"}), 400

    user_id = data.get('user_id')
    task_count = data.get('task_count')
    tasks = data.get('tasks', [])

    if task_count is None or len(tasks) != task_count:
        return jsonify({"status": "error", "message": "Task count mismatch"}), 400

    send_tasks_to_db(user_id, tasks)
    send_tasks_to_discord(user_id, tasks)

    return jsonify({"status": "success", "message": "Tasks submitted successfully!"})


if __name__ == '__main__':
    app.run(debug=True)