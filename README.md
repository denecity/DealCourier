2024 Denis Titov
dtitov@ethz.ch

This is a program that automatically scrapes the plattform tutti.ch (for now) for configured items and saves and sends notifications about listings that it deems especially good. It heavily uses openai api for classification of listings.

Step-by-step guide (hopefully):
1. Get an openai-api key and enable all chatgpt 4o, 4o-mini and embedding tools for your project (you might need other tools if i forget to add them there. look in the config for the tools used)
2. Get a pushbullet account and api key to receive notifications
3. Paste both of them into the config (hopefully i will do it differently soon)
4. understand the configuration structure. hopefully you will only need to modify the actual config.yaml
5. configure your searches/items in the config
6. configure the prompting. maybe i will get the prompting to work well with a one-size-fits-all prompt but you can experiment arround
7. start "DealCourier.py". this will handle the scheduling, scraping and evaluating. it should do everything automatically.
8. after verifying that this works, put it on a server or raspberry and enjoy the deals :3