import asyncio
import random
import sys
from timer import Timer
import json
# 10-second timer
DELAY = 10

class Gossip():
    def __init__(self, loop, members, port=5000):
        self.port = port
        self.members = set(members)
        self.loop = loop
        coro = asyncio.start_server(self.data_received, '127.0.0.1', port, loop=loop)
        self.server = loop.run_until_complete(coro)
        print('Gossip Server started at {} with peers:{}'.format(self.server.sockets[0].getsockname(), self.members))
        self.timer = Timer(DELAY, self.scheduler, self.loop)


    async def data_received(self, reader, writer):
        data = await reader.read(100)
        message = data.decode()
        addr = writer.get_extra_info('peername')
        print("Received %r from %r" % (message, addr))
        if message=='ack':
            print("Sending: %r" % message)
            writer.write(data)
            await writer.drain()
            writer.close()
        else:
            message=json.loads(str(message))
            if message["msg"]=='failed':
                print('{} node failed, deregistering it from the local membership table'.format(message["port"]))
                self.members.remove(int(message["port"]))
                msg="deleted"
                data=msg.encode()
                print("Sending: %r" % message)
                writer.write(data)
                await writer.drain()
                writer.close()

            elif message["msg"]=='ping_req':
                resp = await data_send('ack', int(message["port"]), self.loop)
                if resp == 'ack':
                    msg="ack_res"
                    data=msg.encode()
                    print("Sending: %r" % message)
                    writer.write(data)
                    await writer.drain()
                    writer.close()   
                else:
                    msg="notreceived"
                    data=msg.encode()
                    print("Sending: %r" % message)
                    writer.write(data)
                    await writer.drain()
                    writer.close()
        
            


    def stop(self):
        self.server.close()

    
    async def disseminate(self, failed_node):
        print('Disseminating to all members...')
        #lop=asyncio.get_event_loop()
        for node in self.members:
            msg={'msg':'failed','port':int(failed_node)}
            #lop.run_until_complete(data_send(msg,int(node),self.loop))
            resp = await data_send(json.dumps(msg),int(node),self.loop)
            if resp == 'deleted':
                print('{} deleted the node {} from its membership'.format(node,failed_node))
            else:
                print('no response for dissemination of node {} from {}'.format(failed_node,node))
            #  notify all peers to remove the failed node from their membership.
            print(node)



    async def scheduler(self):
        print('Scheduler is running...')
        print('Members:{}'.format(self.members))
        # Get a random member to ping directly.
        node = random.sample(self.members, 1)[0]
        resp = await data_send('ack', int(node), self.loop)
        if resp == 'ack':
            print('{} is alive.'.format(node))
            return
        else:
            print('Direct ping call to {} was failed'.format(node))
        
        if len(self.members) <= 1:
            print('You only have one member. So, no need to ask for others.')
            return

        # Get random k member(s) to ping_req indirectly.
        temp_members = self.members.copy()
        
        # Remove the ping node from the member list.
        temp_members.remove(node)

        # Get a random member to send ping_req.
        node1 = random.sample(temp_members, 1)[0]
        #  implement indirect ping_req message to a peer via data_send().
        # If the peer did not get 'ack' from ping_req meaning the node is down, then call disseminate().
        msg={'msg':'ping_req','port':int(node)}
        resp= await data_send(json.dumps(msg),int(node1),self.loop)
        if resp == 'ack_res':
            print('{} is alive indirectly, ack received from {}'.format(node,node1))
        else:
            print('indirect ping failed for {}, desseminating it'.format(node))
            self.members.remove(int(node))
            await disseminate(node)


        self.tmer = Timer(DELAY, self.scheduler, self.loop)


async def data_send(message, port, loop):
    reader, writer = await asyncio.open_connection('127.0.0.1', port, loop=loop)
    print('Sending: {}'.format(message))
    writer.write(message.encode())

    data = await reader.read(100)
    print('Received: %r' % data.decode())
    writer.close()


loop = asyncio.get_event_loop()
port = sys.argv[1]
peers = sys.argv[2]
peers = peers.split(",")
gossip = Gossip(loop, peers, port)
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

gossip.stop()
loop.run_until_complete(gossip.server.wait_closed())
loop.close()