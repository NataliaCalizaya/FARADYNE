from apscheduler.schedulers.background import BackgroundScheduler
from .cleanup import cleanup_temp_files

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_temp_files, 'cron', hour=2)

def dummy_version_job():
    pass

scheduler.add_job(dummy_version_job, 'cron', hour=3)

def start():
    scheduler.start()

def shutdown():
    scheduler.shutdown()
