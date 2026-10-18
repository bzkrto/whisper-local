"""Shared research curriculum; classification schedules documents, never user commands."""
from ..common import fold

FOCUS_TOPICS = {
    'security': 'Cybersecurity secure coding dependency security logging input validation defensive testing',
    'context': 'Türkçe NLP intent detection entity extraction multi turn dialogue context evaluation',
    'memory': 'RAG retrieval knowledge processing source grounded memory evaluation',
    'agent': 'LLM tool calling agent planning error reflection regression testing',
    'deep_learning': 'Deep learning transformers fine tuning dataset evaluation overfitting',
}
FOCUS_SEEDS = [
    (FOCUS_TOPICS['security'], 'https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html'),
    (FOCUS_TOPICS['security'], 'https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html'),
    (FOCUS_TOPICS['security'], 'https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html'),
    (FOCUS_TOPICS['context'], 'https://docs.ollama.com/capabilities/structured-outputs'),
    (FOCUS_TOPICS['memory'], 'https://docs.ollama.com/capabilities/embeddings'),
    (FOCUS_TOPICS['agent'], 'https://docs.ollama.com/capabilities/tool-calling'),
    (FOCUS_TOPICS['deep_learning'], 'https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial'),
]

def track(topic):
    value=fold(topic)
    if any(term in value for term in ('cybersecurity','siber','security','owasp','nist','guvenlik')):return 'security'
    groups=(('context',('turkce','dialogue','diyalog','intent','niyet','entity','baglam','context')),
            ('memory',('retrieval','rag ','knowledge','hafiza','memory','bilgi isleme','embedding')),
            ('agent',('agent','ajan','tool calling','planning','planlama','reflection','regression','test','python','ollama')),
            ('deep_learning',('deep learning','derin ogrenme','fine tuning','transformer','dataset','overfitting')))
    return next((key for key,terms in groups if any(term in value for term in terms)), 'general')

def target(number):
    # Four focused turns, one exploratory turn. Context receives two focused turns.
    return ('context','memory','agent','context','general','deep_learning','memory','agent','context','general')[number%10]

def priority_sql(column, number):
    wanted=target(number)
    if wanted=='general':return ''
    # Only constant curriculum labels enter SQL; never user or internet text.
    labels=[topic for topic in FOCUS_TOPICS.values() if track(topic)==wanted]
    clauses=' OR '.join(column+"='"+label.replace("'","''")+"'" for label in labels)
    return 'CASE WHEN ('+clauses+') THEN 0 ELSE 1 END,'


def primary_focus_url(url):
    from urllib.parse import urlsplit
    parsed=urlsplit(url)
    hosts={'docs.ollama.com','docs.pytorch.org','docs.python.org','docs.langchain.com','arxiv.org','learn.microsoft.com',
           'cheatsheetseries.owasp.org','owasp.org','www.nist.gov','csrc.nist.gov','www.cisa.gov'}
    return parsed.hostname in hosts or (parsed.hostname=='huggingface.co' and parsed.path.startswith(('/docs/','/learn/')))
