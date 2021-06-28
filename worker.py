import logging
from utilities import *
from threading import Timer

try:
  import pync
except ImportError:
  pync = None


class NotificationData:

  def __init__(self):
    self.isOnline = False
    self.notifyTimer = None


# ['action', {'add': 'relay'}, [{u'status': u'ERROR', u'message': {u'conversation': u'Test'}, u'key': {u'remoteJid': u'3456345@s.whatsapp.net', u'fromMe': False, u'id': u'62EC04FB60FFBD8A284C28E823EE2D5E'}, u'messageTimestamp': u'1560598969'}]]
class Worker:
  wa = None
  subscribeListFile = None
  presenceFile = None
  notificationFile = None
  notificationList = {}
  subscriberList = {}
  subscriberId = None
  isSubscribed = False
  onlineNotificationDurationSecs = 180

  def __init__(self, subscribeListFile, presenceFile, notificationFile):
    self.subscribeListFile = subscribeListFile
    self.presenceFile = presenceFile
    self.notificationFile = notificationFile

  def subscribe(self):
    logging.info("Subscribe list file: %s" % self.subscribeListFile)
    try:
      with open(self.subscribeListFile) as f:
        lineList = f.readlines()
      for line in lineList:
        line = line.strip()
        info = line.split(",")
        number = info[0]
        id = info[1]
        self.addToSubscriberList(number, id)
        self.sendSubscribe(str.strip(number))
    except:
      logging.info("Subscribe list not present")
      raise

    try:
      with open(self.notificationFile) as f:
        lineList = f.readlines()
      for line in lineList:
        line = line.strip()
        self.notificationList[line] = NotificationData()
    except:
      logging.info("Notification list not present")

  def addToSubscriberList(self, number, id):
    self.subscriberId = id
    self.subscriberList[number] = self.subscriberId
    logging.info("Subscriberid for %s is %s" % (number, self.subscriberList[number]))

  def addNewSubscribe(self, jid):
    number = self.getUserIdIfUser(jid)
    if number in self.subscriberList:
      logging.info("Subscriber already has presence")
      return False
    with open(self.subscribeListFile, "a+") as pFile:
      pFile.write('%s\n' % number)
    self.addToSubscriberList(number)
    self.sendSubscribe(number)
    logging.info("Added the new subscriber")
    return True

  def sendSubscribe(self, userId):
    logging.info('Subsrcibing for %s' % userId)
    messageTag = str(getTimestampMs())
    message = ('%s,,["action", "presence", "subscribe", "%s@c.us"]' % (messageTag, userId))
    logging.info(message)
    self.wa.ws.send(message)

  def notifyLongOnline(self, userId):
    if pync:
      pync.Notifier.notify("{} is online for {}s".format(userId, self.onlineNotificationDurationSecs), sound='Bell',
                           title='Online')

  def handleNotification(self, userId, pType):
    if userId not in self.notificationList:
      return
    if pType == "available":
      if self.notificationList[userId].isOnline:
        return

      notifyTimer = Timer(self.onlineNotificationDurationSecs, lambda: self.notifyLongOnline(userId))
      notifyTimer.start()
      self.notificationList[userId].notifyTimer = notifyTimer
      self.notificationList[userId].isOnline = True

    else:
      if not self.notificationList[userId].isOnline:
        return
      self.notificationList[userId].isOnline = False
      self.notificationList[userId].notifyTimer.cancel()

  def writePresenceToFilefromJson(self, presenceInfo):
    userId = self.getUserIdIfUser(presenceInfo["id"])
    presencetype = presenceInfo["type"]
    presenceTime = getTimeString('Asia/Kolkata')
    self.writePresenceToFile(userId, presencetype, presenceTime)
    self.handleNotification(userId, presencetype)

  def writePresenceToFile(self, userId, pType, pTime):
    with open(self.presenceFile, "a+") as pFile:
      if userId in self.subscriberList:
        pFile.write('%s,%s,%s,%s\n' % (userId, pType, str(pTime), self.subscriberList[userId]))
      else:
        pFile.write('%s,%s,%s,%s\n' % (userId, pType, str(pTime), "None"))

  def getUserIdIfUser(self, sender):
    jid = sender.split('@')[0]
    logging.debug("Jid: %s" % jid)
    splitList = jid.split('-')
    if len(splitList) > 1:
      logging.info("Seems message from group: %s" % sender)
      raise ValueError("Sender seems a group")
    return splitList[0]

  def handleConversation(self, sender, message):
    userId = self.getUserIdIfUser(sender)
    logging.info("UserId: %s, Message:%s" % (userId, message))
    if message != None and message.lower() == "add me":
      isNewAdd = self.addNewSubscribe(sender)
      time.sleep(2)
      if isNewAdd:
        self.wa.sendTextMessage(userId, "Done")
      else:
        self.wa.sendTextMessage(userId, "You are already added.")

    if message != None and message.lower() == "who am i":
      time.sleep(2)
      if userId in self.subscriberList:
        subscriberId = self.subscriberList[userId]
        self.wa.sendTextMessage(userId, subscriberId)
      else:
        self.wa.sendTextMessage(userId, "Sorry you are not included in the list.")

  def handleIfConversation(self, messageJson):
    logging.info("Worker %s" % messageJson)
    if isinstance(messageJson, list) and len(messageJson) > 2:
      if messageJson[0] == 'action':
        metaData = messageJson[1]
        if (metaData is not None) and (isinstance(metaData, object)):
          if 'add' not in metaData:
            logging.info("Action untracked metadata %s" % metaData)
          else:
            if metaData['add'] != 'relay':
              logging.info("Action untracked add metadata %s" % metaData['add'])
            else:
              actionJson = messageJson[2][0]
              if 'key' not in actionJson:
                logging.info('key not present in add relay')
              else:
                sender = actionJson['key']['remoteJid']
                if 'conversation' in actionJson['message']:
                    message = actionJson['message']['conversation']
                    self.handleConversation(sender, message)
        else:
          logging.info("Action metadata not json: %s" % metaData)
      else:
        logging.info("Non tracked action: %s" % messageJson[0])
        logging.info("Value: %s" % messageJson[1])
        logging.info("ValueNext: %s" % messageJson[2])
