# coding: utf-8
# Code © WitcherGeralt, 2012.
# Originally coded for BlackSmith bot mark.2
# Installation:
# Add a field named ALIVE_KEEPER_ENABLED in the main config file and set it's value to True in order to enable the keeper.

"""
Makes the transport ping itself, so it can detect connection hang
It's also can be useful for Openfire administrators
in case if the transport suddenly disconnects
"""

def alive_keeper():
	logger.debug("alive_keeper has started!")

	def alive_keeper_answer(cl, stanza):
		logger.debug("alive_keeper: answer received, continuing iteration")
		Component.aKeeper = 0

	while True:
		time.sleep(60)
		thrIds = [x.name for x in threading.enumerate()]
		if not hasattr(Component, "aKeeper"):
			Component.aKeeper = 0

		if Component.aKeeper > 3:
			logger.error("alive_keeper: answer wasn't received more than 3 times!")
			Print("No answer from the server, restarting...")
			disconnectHandler()
		else:
			logger.debug("alive_keeper: sending request")
			Component.aKeeper += 1
			iq = xmpp.Iq("get", to=TransportID, frm=TransportID)
			iq.addChild("ping", namespace=xmpp.NS_PING)
			sender(Component, iq, cb=alive_keeper_answer)


if isdef("ALIVE_KEEPER_ENABLED") and ALIVE_KEEPER_ENABLED:
	registerHandler("evt01", alive_keeper)
else:
	del alive_keeper