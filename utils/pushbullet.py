import yaml
import os
from pushbullet import Pushbullet
import logging

# this script sets up the pushbullet connection and enables the sending of notifications

def send_notification(title, message, API_KEY):
    pb = Pushbullet(API_KEY)
    pb.push_note(title, message)
    logging.info("Notification: '" + title + ": " + message + "' sent successfully!")
    return


def send_notification_from_df(data, pushbullet_api_key):
    for index in range(len(data)):

        title = data.loc[index, "title"]
        message = "PRICE: " + str(data.loc[index, "price"]) + ", VALUE: " + str(data.loc[index, "total_value"]) + "    " + data.loc[index, "url"]

        send_notification(title,message ,API_KEY=pushbullet_api_key)

