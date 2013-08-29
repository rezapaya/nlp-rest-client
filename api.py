from flask import Flask
from flask.ext import restful
from nlp_client.services import *

app = Flask(__name__)
api = restful.Api(app)

api.add_resource(ParsedXmlService,          '/doc/<string:doc_id>/xml')
api.add_resource(ParsedJsonService,         '/doc/<string:doc_id>/json')
api.add_resource(AllNounPhrasesDemoService, '/doc/<string:doc_id>/nps')
api.add_resource(CoreferenceCountsService,  '/doc/<string:doc_id>/corefs')
api.add_resource(SolrPageService,           '/doc/<string:doc_id>/solr')
api.add_resource(SentimentService,          '/doc/<string:doc_id>/sentiment')
api.add_resource(SolrWikiService,           '/wiki/<string:doc_id>/solr')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
