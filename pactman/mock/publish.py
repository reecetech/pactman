from pactman.verifier.broker_pact import PactBrokerConfig

# NOTE: this code is a WIP, it's not used yet


class Publisher:
    def __init__(self, broker: PactBrokerConfig):
        self.broker = broker
        self.nav = self.broker.get_broker_navigator()

    def publish_pact(self, pact, version, tags):
        # there's no direct link from the broker root to a pacticipant, so we go via pb:latest-version
        tagger = self.nav["latest-version"](pacticipant=pact["consumer"])["pacticipant"][
            "version-tag"
        ]
        for tag in tags:
            tagger(tag=tag, version=version).upsert({})

        self.nav["publish-pact"](
            consumer=pact["consumer"], provider=pact["provider"], version=version
        )
