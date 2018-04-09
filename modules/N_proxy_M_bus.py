"""Opens a proxy bus between 2 ports for a N-proxy-M PubSub pattern

Similar to a ROS topic (named bus)
TODO: register somewhere for a bus overview"""

# Copyright (c) Stef van der Struijk.
# License: GNU Lesser General Public License


import sys
import zmq
# from zmq import Context
from smooth_data import SmoothData
import traceback
import logging


class ProxyPub:
    def __init__(self, address='127.0.0.1', port_pubs='5570', port_subs='5571',
                 data_func='trailing_moving_average'):
        # self.context = Context.instance()
        # 2 sockets, because we can only bind once to a socket (as opposed to connect)
        self.url1 = "tcp://{}:{}".format(address, port_pubs)
        self.url2 = "tcp://{}:{}".format(address, port_subs)

        # don't duplicate the message, just pass through
        if not data_func:
            self.xpub_xsub_proxy()

        # apply function to data
        else:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.pub_sub_function(data_func))
            # self.pub_sub_function(data_func)

    # N publishers to 1 sub; proxy 1 sub to 1 pub; publish to M subscribers
    def xpub_xsub_proxy(self):
        print("Init sockets")
        # Socket subscribing to publishers
        ctx = zmq.Context.instance()
        frontend_pubs = ctx.socket(zmq.XSUB)
        frontend_pubs.bind(self.url1)

        # Socket publishing to subscribers
        backend_subs = ctx.socket(zmq.XPUB)
        backend_subs.bind(self.url2)
        
        print("Try: Proxy... CONNECT!")
        zmq.proxy(frontend_pubs, backend_subs)
        print("CONNECT successful!")

    # smooth data
    async def pub_sub_function(self, data_func):  # async
        print("Init sockets")
        from zmq.asyncio import Context
        import json
        # Socket subscribing to publishers
        # ctx = zmq.Context.instance()
        ctx = zmq.asyncio.Context.instance()
        frontend_pubs = ctx.socket(zmq.SUB)
        frontend_pubs.bind(self.url1)
        frontend_pubs.setsockopt(zmq.SUBSCRIBE, b'')

        # Socket publishing to subscribers
        backend_subs = ctx.socket(zmq.PUB)
        backend_subs.bind(self.url2)

        # class with data smoothing functions
        smooth_data = SmoothData()
        # get the function we need to pass data to
        smooth_func = getattr(smooth_data, data_func)

        # await messages
        print("Awaiting FACS data...")
        # without try statement, no error output
        try:
            # keep listening to all published message on topic 'facs'
            while True:
                [topic, msg] = await frontend_pubs.recv_multipart()
                # print(msg_sub)
                msg = json.loads(msg.decode('utf-8'))
                facs = await smooth_func(msg['data']['facs'], queue_no=0)
                head_pose = await smooth_func(msg['data']['head_pose'], queue_no=1)
                # put new data in msg dict
                msg['facs'] = facs
                msg['head_pose'] = head_pose
                # encode as string
                msg = json.dumps(msg)

                await backend_subs.send_multipart([topic, msg.encode('utf-8')])

        except:
            print("Error with sub")
            # print(e)
            logging.error(traceback.format_exc())
            print()



if __name__ == '__main__':
    # get ZeroMQ version
    print("Current libzmq version is %s" % zmq.zmq_version())
    print("Current  pyzmq version is %s" % zmq.pyzmq_version())

    print("Arguments given: {}".format(sys.argv))
    print("0, 2, or 3 extra arguments are expected (port_pubs, port_subs, (address)), e.g.: 5570 5571 127.0.0.1")

    # no arguments
    if len(sys.argv) == 1:
        ProxyPub()

    # local network, only ports
    elif len(sys.argv) == 3:
        ProxyPub(port_pubs=sys.argv[1], port_subs=sys.argv[2])

    # full network control
    elif len(sys.argv) == 4:
        ProxyPub(port_pubs=sys.argv[1], port_subs=sys.argv[2], address=sys.argv[3])

    else:
        print("Received incorrect number of arguments")