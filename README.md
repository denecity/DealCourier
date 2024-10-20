2024 Denis Titov
dtitov@ethz.ch

This is a program that automatically scrapes the plattform tutti.ch (for now) for your items of, saves the best deals and sends notifications right to your phone so you can be the first one to react. It heavily uses openai api for classification and evaluation of listings. It is built to be run on small servers like a raspberry pi.

Step-by-step guide:
1. Get an openai-api key and enable all chatgpt 4o, 4o-mini and embedding tools for your project.
2. Get a pushbullet account and api key to receive notifications.
3. Paste both of them into the config.
4. understand the configuration structure. You will only need to modify the actual config.yaml
5. configure your searches/items in the config
6. configure the prompting. maybe i will get the prompting to work well with a one-size-fits-all prompt but you can experiment arround
7. run init.py once. this will initialize the logging and database.
8. then set up a cronjob or other scheduling to execute scrape.py
