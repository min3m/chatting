from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChattingUser


class ChattingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        # DB에서 오프라인
        await self.update_user_status_disconnect()

    async def receive_json(self, content, **kwargs):
        # 인증 확인
        if not await self.is_auth():
            if content['token'] is not None:
                user_data = await self.auth(content['token'])
                if user_data is None:
                    await self.close()
                    return
                self.user_id = user_data['id']
                self.user_nickname = user_data['nickname']

                # DB에 최초 접속이면 추가, 기존이면 온라인 갱신 및 채널 갱신.
                await self.update_user_status_connect()
                await self.send_json({"message": "You have successfully logged"})
                return
            else:
                await self.close()
                return

        # 인증 후 일반 메시지
        target_nickname = content['target_nickname']
        target_channel_name = await self.get_target_channel(target_nickname)
        if target_channel_name is None:
            await self.send_json({'error': 'No User or Offline'})
        else:
            data = {
                "type": "chat_message",
                "message": content['message'],
                "from": self.user_nickname
            }
            await self.channel_layer.send(target_channel_name, data)  #대상에게 보냄
            await self.send_json(data)  # 자기자신에게도 보냄

    # my function

    async def chat_message(self, event):
        # 차단 조회 후 전송
        from_nickname = event['from']
        is_blocked = await self.is_blocked_user(from_nickname)
        if not is_blocked:
            await self.send_json(event)

    # 인증 서버에서 인증 받아 오는 함수,
    async def auth(self, token):
        if True:  # TODO: 인증 성공 시
            return {  # TEST CODE
                'id': token,
                'nickname': token + "_test_id",
            }
        else:
            return None

    @database_sync_to_async
    def get_target_channel(self, target_nickname):
        query = ChattingUser.objects.filter(nickname=target_nickname)
        if query.count() == 0:
            return None
        user = query.first()
        if not user.is_online:
            return None

        return user.channel_name

    @database_sync_to_async
    def update_user_status_connect(self):
        query = ChattingUser.objects.filter(id=self.user_id)
        if query.count() == 0:
            ChattingUser.objects.create(id=self.user_id, nickname=self.user_nickname, channel_name=self.channel_name,
                                        is_online=True)
        else:
            user = query.first()
            user.is_online = True
            user.channel_name = self.channel_name
            user.save()

    @database_sync_to_async
    def update_user_status_disconnect(self):
        query = ChattingUser.objects.filter(id=self.user_id)
        user = query.first()
        user.is_online = False
        user.channel_name = None
        user.save()

    @database_sync_to_async
    def is_blocked_user(self, from_nickname):
        from_user = ChattingUser.objects.get(nickname=from_nickname)
        if ChattingUser.objects.get(id=self.user_id).blocked_users.contains(from_user):
            return True
        else:
            return False


    @database_sync_to_async
    def is_auth(self):
        query = ChattingUser.objects.filter(channel_name=self.channel_name)
        if query.count() == 0:
            return False
        return True