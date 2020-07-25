import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram
from telegram import ChatAction
import requests
import sys, os, string, random, shutil, json, zipfile, time
from os import listdir
from os.path import isfile, join
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

PORT = os.environ.get("PORT")
MODE = os.environ.get("MODE")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") + "/" + TOKEN
IMGUR_CLIENT = os.environ.get("IMGUR_CLIENT")

#Used for callbacks
# Stages
FIRST, SECOND = range(2)
# Callback data
ONE, TWO, THREE, FOUR = range(4)


def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

def ImgurUpload(Path):
    hash_list = []
    #Get a list of all files in the given path
    files = [f for f in listdir(Path) if isfile(join(Path, f))]
    if len(files) == 0:
        return 0
    #As per Imgur documentation, upload each image one by one and grab its deletehash ID
    for file in files:
        with open(os.path.join(Path, file),'rb') as handle:
            r = requests.post("https://api.imgur.com/3/upload", headers={'Authorization': f'Client-ID {IMGUR_CLIENT}'},files={'image': handle.read() } )
            hash_list.append(r.json()['data']['deletehash'])
    #Finally, create a new album using the deletehash[] ids
    r = requests.post("https://api.imgur.com/3/album", headers={'Authorization': f'Client-ID {IMGUR_CLIENT}'}, data={"deletehashes[]": hash_list}).json()
    return f"https://imgur.com/a/{r['data']['id']}", r['data']['deletehash']

def ImgurDelete(update, context):
    query = update.callback_query
    DeleteHASH = query['message']['reply_markup']['inline_keyboard'][0][0]['text'].split(" ")[4]
    #This is how mgur wants the api to be like
    if requests.request("DELETE", url=f"https://api.imgur.com/3/album/{DeleteHASH}", headers={'Authorization': f'Client-ID {IMGUR_CLIENT}'}, files={}, data={}, allow_redirects=True).json()['success'] == True:
        query.answer()
        query.edit_message_text(
            text=f"*Imgur Album Deleted - Please give it a minute to fully delete*", parse_mode=telegram.ParseMode.MARKDOWN
        )
    else:
        query.answer()
        query.edit_message_text(
            text=f"*There was an error attempting to delete the album...*", parse_mode=telegram.ParseMode.MARKDOWN
        )
    return ConversationHandler.END

# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    update.message.reply_text("*Need specific details about your Telegram account? I can help!\nType '/info' for full details. Type '/help' for a list of commands.*",parse_mode=telegram.ParseMode.MARKDOWN)

#---------- COMMANDS: ----------------

def forwardinfo(update, context):
    #get the info of the forwarded user/bot
    userObj = update.message.forward_from
    if userObj == None:
        update.message.reply_text(text="*This user has Anonymous Forwarding turned on\n\nRead about it*:\nhttps://telegram.org/blog/unsend-privacy-emoji#anonymous-forwarding", parse_mode=telegram.ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text="""*UserID*: {}\n*First Name*: {}\n*Last Name*: {}\n*Username*: @{}\n*Is a bot*: {}\n*Link*: https://t.me/{}\n*Language*: {}\n""".format(
                userObj.id, userObj.first_name, userObj.last_name, userObj.username, userObj.is_bot, userObj.username, userObj.language_code
        ), parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)

        #Its better copy and paste the photo code again than put it in its own function
        userphotos = context.bot.get_user_profile_photos(userObj.id)

        update.message.reply_text(text= "*Getting Photo(s), give us a minute.*", parse_mode=telegram.ParseMode.MARKDOWN)
        context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        randName = randomString()
        foldPath = os.path.join(os.getcwd(), 'temp', randName)
        os.makedirs(os.path.join(foldPath, 'photos'))

        imgurLink = None

        if userphotos.total_count == 0:
            context.bot.send_message(chat_id=update.message.chat_id, text="*Total Number of Profile Photo(s)*: {}".format(userphotos.total_count), parse_mode=telegram.ParseMode.MARKDOWN)
        else:
            for photo in userphotos['photos']:
                fileID = photo[-1]['file_id']
                context.bot.get_file(fileID).download(custom_path=os.path.join(foldPath, 'photos', f"{userphotos['photos'].index(photo)}.jpg"))

            imgurLink = ImgurUpload(os.path.join(foldPath, 'photos'))
            msg = ""
            msg += f"*Imgur Album of all their Profile Photo(s)*: {imgurLink[0]}\n\n*Zipped Copy of their Profile Photo(s)*"

            with zipfile.ZipFile(os.path.join(foldPath, f"{randName}.zip"), 'w', compression=zipfile.ZIP_DEFLATED) as z:
                files = [f for f in listdir(os.path.join(foldPath, 'photos')) if isfile(join(os.path.join(foldPath, 'photos'), f))]
                for file in files:
                    z.write(os.path.join(foldPath, 'photos', file))

            context.bot.send_message(chat_id=update.message.chat_id, text="*Total Number of Profile Photo(s)*: {}".format(userphotos.total_count), parse_mode=telegram.ParseMode.MARKDOWN)
            context.bot.send_message(chat_id=update.message.chat_id, text="*Current Photo*", parse_mode=telegram.ParseMode.MARKDOWN)
            context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)

            keyboard = [
            [InlineKeyboardButton(f"Delete Imgur Album? - {imgurLink[1]}", callback_data=str(ONE))]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            with open(os.path.join(foldPath, 'photos', '0.jpg'), 'rb') as p:
                context.bot.send_photo(chat_id=update.message.chat_id, photo=p)

            with open(os.path.join(foldPath, f"{randName}.zip"), 'rb') as z:
                context.bot.send_document(chat_id=update.message.chat_id, document=z)

            context.bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup, disable_web_page_preview=True)


        try:
            shutil.rmtree(foldPath)
        except Exception as e:
            pass

        return FIRST



def currinfo(update, context):
    userObj = update.message.from_user
    update.message.reply_text(text="""*UserID*: {}\n*First Name*: {}\n*Last Name*: {}\n*Username*: @{}\n*Is a bot*: {}\n*Link*: https://t.me/{}\n*Language*: {}\n*If you have trouble copying and pasting a specific detail, type the command to get that specific detail (refer to /help for the list) and just copy & paste the message.*""".format(
            userObj.id, userObj.first_name, userObj.last_name, userObj.username, userObj.is_bot, userObj.username, userObj.language_code
    ), parse_mode=telegram.ParseMode.MARKDOWN)
    context.bot.send_message(chat_id=update.message.chat_id, text="*If you want your profile picture(s), type '/pic'*", parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)


def userID(update, context):
    update.message.reply_text(text= str(update.message.from_user.id))


def firstName(update, context):
    update.message.reply_text(text= str(update.message.from_user.first_name))

def lastName(update, context):
    update.message.reply_text(text= str(update.message.from_user.last_name))


def username(update, context):
    update.message.reply_text(text= str(update.message.from_user.username))


def is_bot(update, context):
    update.message.reply_text(text= str(update.message.from_user.is_bot))


def profpic(update, context):
    userphotos = context.bot.get_user_profile_photos(update.message.from_user.id)

    update.message.reply_text(text= "*Getting Photo(s), give us a minute.*", parse_mode=telegram.ParseMode.MARKDOWN)
    context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    randName = randomString()
    foldPath = os.path.join(os.getcwd(), 'temp', randName)
    os.makedirs(os.path.join(foldPath, 'photos'))

    imgurLink = None

    if userphotos.total_count == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text="*Total Number of Profile Photo(s)*: {}".format(userphotos.total_count), parse_mode=telegram.ParseMode.MARKDOWN)
    else:
        for photo in userphotos['photos']:
            fileID = photo[-1]['file_id']
            context.bot.get_file(fileID).download(custom_path=os.path.join(foldPath, 'photos', f"{userphotos['photos'].index(photo)}.jpg"))

        imgurLink = ImgurUpload(os.path.join(foldPath, 'photos'))
        msg = ""
        msg += f"*Imgur Album of all their Profile Photo(s)*: {imgurLink[0]}\n\n*Zipped Copy of their Profile Photo(s)*"

        with zipfile.ZipFile(os.path.join(foldPath, f"{randName}.zip"), 'w', compression=zipfile.ZIP_DEFLATED) as z:
            files = [f for f in listdir(os.path.join(foldPath, 'photos')) if isfile(join(os.path.join(foldPath, 'photos'), f))]
            for file in files:
                z.write(os.path.join(foldPath, 'photos', file))

        context.bot.send_message(chat_id=update.message.chat_id, text="*Total Number of Profile Photo(s)*: {}".format(userphotos.total_count), parse_mode=telegram.ParseMode.MARKDOWN)
        context.bot.send_message(chat_id=update.message.chat_id, text="*Current Photo*", parse_mode=telegram.ParseMode.MARKDOWN)
        context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)

        keyboard = [
            #Add the delete hash to the imgur button so we can parse it later if the user wants to delete it
        [InlineKeyboardButton(f"Delete Imgur Album? - {imgurLink[1]}", callback_data=str(ONE))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        with open(os.path.join(foldPath, 'photos', '0.jpg'), 'rb') as p:
            context.bot.send_photo(chat_id=update.message.chat_id, photo=p)

        with open(os.path.join(foldPath, f"{randName}.zip"), 'rb') as z:
            context.bot.send_document(chat_id=update.message.chat_id, document=z)

        #Send the message seperately instead of a caption for the zip, otherwise, the InlineKeyboard will not be able to edit it
        context.bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup, disable_web_page_preview=True)

    try:
        shutil.rmtree(foldPath)
    except Exception as e:
        pass

    return FIRST




#-----------DEFAULT:------------

def helpMsg(update, context):
    helplist = ["/info - Gets all general information",
    "/userID - Gets your unique Telegram ID",
    "/firstName - Gets your first name you set on Telegram",
    "/lastName - Gets your last name you set on Telegram",
    "/username - Gets your username you set on Telegram",
    "/is_bot - Replies with a True or False depending if a user is a bot",
    "/help - Displays this help list",
    "/pic - Gets your profile picture(s) in a downloadable format"
    ]

    msg = ""
    for i in helplist:
        msg += "{}\n".format(i)
    update.message.reply_text(text=msg)
    context.bot.send_message(chat_id=update.message.chat_id, text="*If you want to retrieve information about another user, forward a message from that user to me and I will give you their general info, including Telegram ID and profile photo(s)*", parse_mode=telegram.ParseMode.MARKDOWN)

def echo(update, context):
    """Echo the user message."""
    update.message.reply_text("'" + update.message.text + "' *is not a valid command*", parse_mode=telegram.ParseMode.MARKDOWN)

def no_sticker(update, context):
    update.message.reply_text("*You cannot forward a sticker, forward a message instead!*", parse_mode=telegram.ParseMode.MARKDOWN)


def error(update, context):
    update.message.reply_text("*Unable to handle action - Check /help or /info for actions*", parse_mode=telegram.ParseMode.MARKDOWN)
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("pic", profpic), MessageHandler(Filters.forwarded , forwardinfo)],
        states={
            FIRST: [CallbackQueryHandler(ImgurDelete, pattern='^' + str(ONE) + '$')]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    # Add ConversationHandler to dispatcher that will be used for handling
    # updates
    dp.add_handler(conv_handler)

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    #commands
    dp.add_handler(CommandHandler("info", currinfo))
    dp.add_handler(CommandHandler("help", helpMsg))

    dp.add_handler(CommandHandler("userID", userID))
    dp.add_handler(CommandHandler("firstName", firstName))
    dp.add_handler(CommandHandler("lastName", lastName))
    dp.add_handler(CommandHandler("username", username))
    dp.add_handler(CommandHandler("is_bot", is_bot))
    dp.add_handler(CommandHandler("pic", profpic))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.sticker, no_sticker))
    dp.add_handler(MessageHandler(Filters.forwarded , forwardinfo))
    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    if MODE == "local":
        print("In Local Mode - Polling...")
        updater.start_polling()
    elif MODE == "server":
        if not PORT:
            sys.exit("PORT is not set - Check your Environment Variables")
        elif not WEBHOOK_URL:
            sys.exit("WEBHOOK_URL is not set - Check your Environment Variables")

        print("Attempting to listen on port {}".format(PORT))
        updater.start_webhook(listen="0.0.0.0",
                            port=PORT,
                            url_path=TOKEN)
        print("Setting Webhook URL to {} \n".format(WEBHOOK_URL))
        updater.bot.set_webhook(WEBHOOK_URL)
        print("In Server Mode! Listening for incoming messages")

    updater.idle()


if __name__ == '__main__':
    if not TOKEN:
        sys.exit("No Telegram Bot Token Set - Check your Environment Variables")
    elif not MODE:
        sys.exit("No Mode Set - Check Your Environment Variables")
    elif MODE != 'local' and MODE != 'server':
        sys.exit("Invalid Mode Set - Make sure 'MODE' is set to either 'local' (for polling) or 'server' (for webhook)")
    if os.path.exists(os.path.join(os.getcwd(), 'temp')) == False:
        os.mkdir(os.path.join(os.getcwd(), 'temp'))
    elif os.path.exists(os.path.join(os.getcwd(), 'temp')) == True:
        #If the directory exists, delete it and remake it to free up space
        shutil.rmtree(os.path.join(os.getcwd(), 'temp'), ignore_errors=True)
        time.sleep(2)
        os.makedirs(os.path.join(os.getcwd(), 'temp'))
    main()