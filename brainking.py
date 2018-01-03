# coding: utf-8

import time
import json
import os
import sys
import requests
import re
import traceback
import jieba
import Queue
import threading
from lxml import etree
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from databases import db_session, Question


CHARLES_BASE = './charles/'
WATCHED_PATH = os.path.join( os.path.abspath(CHARLES_BASE), 'question.hortor.net/question/fight/')
FIND_QUIZ_FILE = os.path.join(WATCHED_PATH, 'findQuiz')
CHOOSE_FILE = os.path.join(WATCHED_PATH, 'choose')


class QuizAnswer(object):
    def __init__(self, quiz, options):
        self.quiz = quiz
        self.options = options
        self.resolved = False
        self.pages = None
        self.answer = None


    def wordsplit(self, s):
        return list(set(jieba.cut_for_search(s)))

    def _resolve(self):
        allkeys = sum( [self.wordsplit(i) for i in self.options] + [[self.quiz]], [])
        self.pages = self._searchpages(allkeys)

        powers = [self._powervector(option) for option in self.options]
        idxes = [i for i in range(len(self.options))]
        idxes.sort(reverse=True, key=lambda x: powers[x])
        self.answer = idxes
        self.resolved = True

    def getanswer(self):
        if not self.resolved:
            self._resolve()
        return self.answer


    def _searchpages(self, keys):
        pages = {}
        q = Queue.Queue()
        for k in set(keys): q.put(k)

        def _searchpage(s):
            r = requests.get('http://www.baidu.com/s', params={'wd': s}, timeout=3)
            return r.text

        def _worker():
            while True:
                try:
                    k = q.get(block=False)
                    try: 
                        v = _searchpage(k)
                    except requests.ConnectionError:
                        time.sleep(1)
                        v = _searchpage(k)

                    pages[k] = v

                except Queue.Empty:
                    return


        threads = [ threading.Thread(target=_worker) for i in range(3) ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return pages


    def _powervector(self, option):
        quizconent = self._getpagecontent()
        wordvector = self.wordsplit(option)
        wordfrequency = [ self._getwordfrequency(w) for w in wordvector]
        wordcount = [ quizconent.count(w) for w in wordvector]
        wordrate = [ 1.0 * (c+1) / (f+1)  for c, f in zip(wordcount, wordfrequency) ]
        return [quizconent.count(option)] + sorted(wordrate, reverse=True)


    def _getpagecontent(self):
        html = etree.HTML(self.pages[self.quiz])
        lines = html.xpath("//*[@id='content_left']//*/text()")
        return ''.join(lines)

    def _getwordfrequency(self, word):
        html = etree.HTML(self.pages[word])
        textlist = html.xpath('//*[@class="nums"]/text()')
        if textlist:
            text = textlist[0]
            numstr = re.match(ur'百度为您找到相关结果约([\d,]+)个', text).group(1)
            return int(numstr.replace(',', ''))
        else:
            return 0



class QuizHandler(FileSystemEventHandler):
    def __init__(self):
        self.num_find = -1
        self.num_choose = -1
        self.hist = {}

    def on_created(self, event):
        self.on_modified(event)        

    def on_modified(self, event):
        if os.path.samefile(FIND_QUIZ_FILE, event.src_path):
            try:
                self.event_find(event.src_path)
            except Exception as e:
                err = traceback.format_exc()
                print err

        elif os.path.samefile(CHOOSE_FILE, event.src_path):
            try:
                self.event_choose(event.src_path)
            except Exception as e:
                err = traceback.format_exc()
                print err

        else:
            pass


    def event_find(self, path):
        d = json.loads(open(path).read())
        num = d['data']['num']
        if num != self.num_find:
            self.num_find = num
            self.question_flush(d)


    def event_choose(self, path):
        d = json.loads(open(path).read())
        num = d['data']['num']
        answer = d['data']['answer']
        if num != self.num_choose:
            self.num_choose = num
            if num in self.hist:
                question = self.hist[num]
                options = json.loads(question.options)
                answers = json.loads(question.answer)
                anstxt = options[answer-1]
                if anstxt not in answers:
                    question.answer = json.dumps(answers + [anstxt])
                    db_session.commit()


    def question_flush(self, d):
        def _ansdisp(idx):
            return chr(ord('A') + idx)

        answerformat = '%s    %s  %s             (%s)'

        quiz = d['data']['quiz']
        options = d['data']['options']
        num = d['data']['num']

        print '\n================================================\n'
        print str(num) + '. ' + quiz
        print 
        for i, op in enumerate(options):
            print '  ' + _ansdisp(i) + '. ' + op
        print 



        question = Question.query.get(quiz)
        if question:
            question.options = json.dumps(options)
        else:
            question = Question()
            db_session.add(question)
            question.quiz = quiz
            question.school = d['data']['school']
            question.type = d['data']['type']
            question.options = json.dumps(options)
            question.answer = json.dumps([])
        db_session.commit()
        self.hist[num] = question

        answers = json.loads(question.answer)
        if set(answers) & set(options):
            anstxt = (set(answers) & set(options)).pop()
            ansidx =  _ansdisp(options.index(anstxt))
            print answerformat % (u'[题库]', ansidx, anstxt, ansidx)

        else:
            anssort = QuizAnswer(quiz, options).getanswer()
            ans = anssort[0]
            print answerformat % (u'[guess]', _ansdisp(ans), options[ans], ' '.join(_ansdisp(i) for i in anssort) )
        
        print
        print 
        print
    

if __name__ == "__main__":
    list(jieba.cut('init'))

    event_handler = QuizHandler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCHED_PATH, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
