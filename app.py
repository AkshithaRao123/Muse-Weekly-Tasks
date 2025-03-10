from flask import Flask, request, render_template, jsonify
import requests
import os
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import threading
import re
load_dotenv()

app = Flask(__name__)

MONGO_URI = os.getenv("MONGO_URI") 

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

GUILD = discord.Object(id=1341366670417203293)
# webhook_url_daily = f"{os.getenv('WEBHOOK_DAILY')}?wait=true"
webhook_url_weekly = f"{os.getenv('WEBHOOK_WEEKLY')}?wait=true"


client = MongoClient(MONGO_URI)
db = client.tasks_db 
user_tasks_weekly_collection = db.user_tasks_weekly
weekly_task_messages_collection = db.weekly_task_messages

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(guild=GUILD)
@commands.is_owner()
async def sync_command(ctx, guild=GUILD):
    await bot.tree.sync(guild=guild)
    await ctx.send("✅ Commands synced successfully!", delete_after = 20)

date_time_today = datetime.datetime.now()
date_today = datetime.date(
    date_time_today.year,
    date_time_today.month,
    date_time_today.day
)
start_of_week = date_today - datetime.timedelta(days=date_today.weekday())
start_of_week = start_of_week.strftime("%d-%m-%Y (%A)")
# date_today = date_time_today.strftime("%d-%m-%Y (%A)")

weekly_channel_id = 1343804943257305140

def send_tasks_to_db(user_id, tasks):

    print("db_fnx")
    for task in tasks:
        task_data = {
            "user_id": user_id,
            "week_start": start_of_week,
            "task_name": task['taskName'],
            "priority": task['priority'],
            "why": task['taskWhy'],
            "how": task['taskHow'],
            "dependencies": task['Dependencies'],
            "great_performance": task['greatPerformance'],
            "good_performance": task['goodPerformance'],
            "bad_performance": task['badPerformance'],
            "estimated_time": f"{task['estimatedTime']['value']} {task['estimatedTime']['unit']}",
            "completed": False
        }
        user_tasks_weekly_collection.insert_one(task_data)

def send_tasks_to_discord(user_id):
    print("discord fnx")

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
    print(map_users)

    user_tasks = list(user_tasks_weekly_collection.find(
            {"user_id": user_id, "week_start": start_of_week}
        ))
    
    print(user_tasks, "--------------------")
    
    embeds = []
    fields = []

    for i, task in enumerate(user_tasks, 0):
        fields.append({
                "name": f"\n\n**Task {i+1}: {task['task_name']}**  |  **Priority:** {task['priority']}",
                "value":f"**Why?:**\n{task['why']}\n"
                        f"**How?:**\n{task['how']}\n"
                        f"**Dependencies:**\n<@{map_users[task['dependencies']]}>\n"
                        f"**Estimated Time:**\n{task['estimated_time']}\n"
                        f"Monitoring performance:\n"
                        f"**Great performance:**\n{task['great_performance']}\n"
                        f"\n"
                        f"**Good performance:**\n{task['good_performance']}\n"
                        f"\n"
                        f"**Bad performance:**\n{task['bad_performance']}\n"
                        f"────────────\n\n",
            })
        
    embeds.append(
            {
                "title": f"📅 Tasks for the week starting: {start_of_week}",
                "description": f"📝 **Tasks added by <@{user_id}>**\n\n",
                "inline": False,
                "fields": fields,
                "color": 0x0059FF,
            }
        )

    payload = {
        "embeds": embeds
    }

    response = requests.post(webhook_url_weekly, json=payload)

    if response.status_code == 200:
        message_data = response.json()  
        message_id = message_data.get("id")
        print("Message ID:", message_id)

        message_details = {
            "user_id": user_id, 
            "week_start": start_of_week, 
            "task_messages": message_id
        }
        weekly_task_messages_collection.insert_one(message_details)

    else:
        print("Failed to send message:", response.text)

class CompletionSelect(discord.ui.Select):
    def __init__(self, user_id, options):
        super().__init__(placeholder="Select tasks to mark as complete", min_values=1, max_values=len(options), options=options)
        self.user_id = user_id
        self.task_messages = list(weekly_task_messages_collection.find({
            "user_id": self.user_id,
            "week_start": start_of_week
        }))

    async def callback(self, interaction: discord.Interaction):
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

        selected_task_names = [re.search(": .+", label).group()[2:] for label in self.values]

        user_tasks_weekly_collection.update_many(
            {"user_id": self.user_id, "task_name": {"$in": selected_task_names}, "week_start": start_of_week},
            {"$set": {"completed": True}}
        )

        # Update the message
        message_id = self.task_messages[-1]["task_messages"]
        if message_id:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url_weekly, session=session) 

                try:
                    message = await webhook.fetch_message(message_id)

                    if message:
                        embed = message.embeds[0]
                        embed.clear_fields()

                        user_tasks = list(user_tasks_weekly_collection.find({"user_id": self.user_id, "week_start": start_of_week}))
                        completed_count = sum(task.get("completed", False) for task in user_tasks)
                        total_tasks = len(user_tasks)
                        completion_percentage = int((completed_count / total_tasks) * 100) if total_tasks > 0 else 0
                        
                        
                        for i, task in enumerate(user_tasks):
                            checkmark = "✅" if task.get("completed", False) else ""
                            embed.add_field(
                                name=f"\n\n**Task {i+1}: {task['task_name']}**   |    **Priority:** {task['priority']} {checkmark}",
                                value=f"**Why?:**\n{task['why']}\n"
                                    f"**How?:**\n{task['how']}\n"
                                    f"**Dependencies:**\n<@{map_users[task['dependencies']]}>\n"
                                    f"**Estimated Time:**\n{task['estimated_time']}\n"
                                    f"Monitoring performance:\n"
                                    f"**Great performance:**\n{task['great_performance']}\n"
                                    f"\n"
                                    f"**Good performance:**\n{task['good_performance']}\n"
                                    f"\n"
                                    f"**Bad performance:**\n{task['bad_performance']}\n"
                                    f"────────────\n\n",
                                inline=False
                            )

                        embed.set_footer(text=f"Completion: {completion_percentage}% ✅")
                        await webhook.edit_message(
                            message_id=message_id,
                            embed=embed
                        )

                        await interaction.response.send_message("✅ Tasks marked as complete!", ephemeral=True)

                except discord.NotFound:
                    await interaction.response.send_message("❌ Could not find the message to edit.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Webhook lacks permission to edit the message.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class CompletionView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

        user_tasks = list(user_tasks_weekly_collection.find({"user_id": user_id, "week_start": start_of_week}))
        print(user_tasks)

        options = [
            discord.SelectOption(label=f"Task {i+1}: {task['task_name']}", value=str(i)+f": {task['task_name']}")
            for i, task in enumerate(user_tasks)
            if not task.get("completed", False)
        ]

        if options:
            self.add_item(CompletionSelect(user_id, options))


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
    send_tasks_to_discord(user_id)

    return jsonify({"status": "success", "message": "Tasks submitted successfully!"})


if __name__ == '__main__':

    # Serve the form pagescheduler.
    @app.route('/form')
    def form():
        user_id = request.args.get('user_id') 
        return render_template('weekly.html', user_id=user_id)
    
    @bot.tree.command(name="task_weekly", description="Submit your weeklyy tasks", guild=GUILD)
    async def task_weekly(interaction: discord.Interaction):
        user_id = interaction.user.id
        # Redirect the user to the Flask server's form page
        form_url = f"http://localhost:5000/form?user_id={user_id}"
        await interaction.response.send_message(f"Please fill out your tasks here: {form_url}", ephemeral=True)

    @bot.tree.command(name="complete_task_weekly", description="Mark completion of your weeklyy tasks", guild=GUILD)
    async def complete_task_weekly(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        await interaction.response.send_message("🔍 Select tasks to mark as complete.", view=CompletionView(user_id), ephemeral=True)

    def run_flask():
        app.run(host="0.0.0.0", port=5000, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()


    bot.run(TOKEN)
    
    

