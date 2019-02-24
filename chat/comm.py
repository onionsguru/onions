from channels.generic.websocket import AsyncWebsocketConsumer
# from asgiref.sync import async_to_sync
import json
from chat import models
import datetime
import pytz

class ChatChannel(AsyncWebsocketConsumer):
    talk_backlog = dict(str())
   
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_id = 'chat_%s' % self.room_id
        user = models.User.objects.all().get(pk=self.user_id)        
        cur_time = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
        time_text = str(cur_time)
        message = f'Welcome~ <b>{user.nickname_text}</b> has joined at <{time_text[:19]}>'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_id,
            self.channel_name
        )

        await self.accept()

        await self.channel_layer.group_send(
            self.room_group_id,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    async def disconnect(self, close_code):
        # Leave room group
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user_id = self.scope['url_route']['kwargs']['user_id']
 
        user = models.User.objects.all().get(pk=self.user_id)        
        message = f'Bye~ <b>{user.nickname_text}</b> has left!'
        is_owner = user.is_owner
        user.delete()     
        
        ch = models.Chatroom.objects.all().get(pk=self.room_id)
        if ch.user_set.count() == 0:
            ch.delete()
        elif is_owner:
            u = ch.user_set.first();
            u.is_owner = True 
            u.save()
        
        await self.channel_layer.group_send(
            self.room_group_id,
            {
                'type': 'chat_message',
                'message': message
            }
        )
        
        await self.channel_layer.group_discard(
            self.room_group_id,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user_id = text_data_json['user']
        user = models.User.objects.all().get(pk=user_id)
        message = f'<b>{user.nickname_text}</b> : {message}'

        try:
            self.talk_backlog[self.room_group_id] = self.talk_backlog[self.room_group_id] + message
        except KeyError:
            self.talk_backlog[self.room_group_id] = ''
            
        # print(f'talk = "{self.talk_backlog[self.room_group_id]}"')
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_id,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    def get_chatters(self, id):
        chatroom = models.Chatroom.objects.all().get(pk=id)
        chatter_list = []
        
        for u in chatroom.user_set.all():
            if u.is_owner:
                chatter_list.append('<b><i>'+ u.nickname_text+ ' (' + u.auth_name + ')</i></b><br>')
            else:
                chatter_list.append(u.nickname_text+' (' + u.auth_name + ')<br>')
        return chatter_list
      
    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        chatter_list = self.get_chatters(self.room_id)

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'chatters': chatter_list
        }))
        
