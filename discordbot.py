import discord
from discord import app_commands
from discord.ext import commands
from pymongo import MongoClient
import re
import os
import datetime
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

GUILD = discord.Object(id=1341366670417203293)

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

weekly_channel_id = 1343804943257305140

class CompletionSelect(discord.ui.Select):
    def __init__(self, user_id, options):
        super().__init__(placeholder="Select tasks to mark as complete", min_values=1, max_values=len(options), options=options)
        self.user_id = user_id
        self.task_messages = list(weekly_task_messages_collection.find({
            "user_id": self.user_id,
            "week_start": start_of_week.strftime("%d-%m-%Y (%A)")
            }))

    async def callback(self, interaction: discord.Interaction):
        selected_task_indices = [int(re.search(r"\d+:", value).group()[:-1]) for value in self.values]
        selected_task_names = [re.search(": .+", label).group()[2:] for label in self.values]

        date_time_today = datetime.datetime.now()
        date_today = datetime.date(
            date_time_today.year,
            date_time_today.month,
            date_time_today.day
        )
        start_of_week = date_today - datetime.timedelta(days=date_today.weekday())
        user_tasks_weekly_collection.update_many(
            {"user_id": self.user_id, "task_name": {"$in": selected_task_names}, "week_start": start_of_week.strftime("%d-%m-%Y (%A)")},
            {"$set": {"completed": True}}
        )

        # Update the message
        message_id = self.task_messages[-1]["task_messages"]
        if message_id:
            channel = bot.get_channel(weekly_channel_id)
            message = await channel.fetch_message(message_id)

            if message:
                embed = message.embeds[0]
                embed.clear_fields()

                user_tasks = list(user_tasks_weekly_collection.find({"user_id": self.user_id, "week_start": start_of_week.strftime("%d-%m-%Y (%A)")}))
                completed_count = sum(task.get("completed", False) for task in user_tasks)
                total_tasks = len(user_tasks)
                completion_percentage = int((completed_count / total_tasks) * 100) if total_tasks > 0 else 0

                for i, task in enumerate(user_tasks, 0):
                    checkmark = "✅" if task.get("completed", False) else ""
                    embed.add_field(
                        name=f"📌 **Task {i+1}: {task['task_name']}**", #          |          🏷 **Priority:** {task['priority'].upper()} {checkmark}",
                        value=f"────────────\n"
                            f"📖 **Why?:**\n{task['why']}\n"
                            f"────────────\n"
                            f"🔍 **How?:**\n{task['how']}\n"
                            f"────────────\n"
                            f"**Dependencies:**\n{task['dependencies']}\n"
                            f"────────────\n"
                            f"⏳ **Estimated Time:**\n{task['estimated_time']}\n"
                            f"────────────\n"
                            f"**Great performance:**\n{task['great_performance']}\n"
                            f"\n"
                            f"**Good performance:**\n{task['good_performance']}\n"
                            f"\n"
                            f"**Bad performance:**\n{task['bad_performance']}\n"
                            f"────────────\n",
                        inline=False
                    )

                embed.set_footer(text=f"Completion: {completion_percentage}% ✅")
                await message.edit(embed=embed)

        await interaction.response.send_message("✅ Tasks marked as complete!", ephemeral=True)


class CompletionView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        date_time_today = datetime.datetime.now()
        date_today = datetime.date(
            date_time_today.year,
            date_time_today.month,
            date_time_today.day
        )
        self.start_of_week = date_today - datetime.timedelta(days=date_today.weekday())

        user_tasks = list(user_tasks_weekly_collection.find({"user_id": user_id, "week_start": self.start_of_week.strftime("%d-%m-%Y (%A)")}))

        options = [
            discord.SelectOption(label=f"Task {i+1}: {task['task_name']}", value=str(i)+f": {task['task_name']}")
            for i, task in enumerate(user_tasks)
            if not task.get("completed", False)
        ]

        if options:
            self.add_item(CompletionSelect(user_id, options))

if __name__ == "__main__":

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.command(guild=GUILD)
    @commands.is_owner()
    async def sync_command(ctx, guild=GUILD):
        await bot.tree.sync(guild=guild)
        await ctx.send("✅ Commands synced successfully!", delete_after = 20)

    @bot.tree.command(name="task_weekly", description="Submit your weekly tasks", guild=GUILD)
    async def task_weekly(interaction: discord.Interaction):
        user_id = interaction.user.id
        # Redirect the user to the Flask server's form page
        form_url = f"http://localhost:5000/form?user_id={user_id}"
        await interaction.response.send_message(f"Please fill out your tasks here: {form_url}", ephemeral=True)

    @bot.tree.command(name="complete_task_weekly", description="Mark completion of your weekly tasks", guild=GUILD)
    async def complete_task_weekly(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        await interaction.response.send_message("🔍 Select tasks to mark as complete.", view=CompletionView(user_id), ephemeral=True)

    bot.run(TOKEN)