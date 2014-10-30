#!/usr/bin/python
# encoding=UTF-8

from collections import deque, Iterable
from itertools import chain
import copy

class Transition(object):
	def __init__(self, label, target, actions=[]):
		self.label = label
		self.target = target
		self.actions = list(actions)

	def appendActions(self, actions):
		self.actions.extend([action for action in actions if action not in self.actions])

	def prependActions(self, actions):
		self.actions[:0] = [action for action in actions if action not in self.actions]

class State(object):
	def __init__(self):
		self.onleave = list()
		self.transitions = set()
		self.id = None

	def addTransition(self, label, target, actions=[]):
		trans = set([t for t in self.transitions if t.label == label and t.target == target])
		if len(trans) > 0:
			for t in trans: t.appendActions(actions)
		else:
			self.transitions.add(Transition(label, target, list(actions)))

class Fsm(object):
	def __init__(self):
		self.entry = None
		self.accepts = set()

	def onenter(self, actions):
		for t in self.entry.transitions:
			t.prependActions(actions)
		return self

	def onleave(self, actions):
		for state in self.accepts:
			state.onleave.extend(actions)
		return self

	def onfinal(self, actions):
		states = self.reachables()
		for state in states:
			trans = [t for t in state.transitions if t.target in self.accepts]
			for t in trans: t.appendActions(actions)
		return self

	def empty(self):
		self.entry = State()
		self.accepts = set([self.entry])
		return self

	def concat(self, b):
		for state in self.accepts:
			state.addTransition(None, b.entry, state.onleave)
		self.accepts = b.accepts
		return self

	def union(self, b):
		entry = State()
		entry.addTransition(None, self.entry)
		entry.addTransition(None, b.entry)
		self.accepts = self.accepts.union(b.accepts)
		self.entry = entry
		return self

	def kleene(self):
		entry = State()
		final = State()
		for state in self.accepts:
			state.addTransition(None, entry, state.onleave)
		entry.addTransition(None, self.entry)
		entry.addTransition(None, final)
		self.entry = entry
		self.accepts = set([final])
		return self

	def reachables(self):
		states = list()
		queue = deque([self.entry])
		while len(queue) > 0:
			state = queue.popleft()
			states.append(state)
			for trans in state.transitions:
				if trans.target not in states and trans.target not in queue:
					queue.append(trans.target)
		return states

	@staticmethod
	def closure(states):
		if not isinstance(states, Iterable): states = [states]
		states = list(states)
		actions = [list() for i in range(0, len(states))]
		queue = deque(states)
		while len(queue) > 0:
			state = queue.popleft()
			# states reachable from [state] via epsilon transitions
			eps_trans = [trans for trans in state.transitions if trans.label is None]
			for trans in eps_trans:
				if trans.target not in states:
					states.append(trans.target)
					actions.append(list(actions[states.index(state)]))
					queue.append(trans.target)
				actions[states.index(trans.target)].extend([a for a in trans.actions if a not in actions[states.index(trans.target)]])
#		print "  closure has length %d: %s" % (len(states), actions)
		return states, actions

class XMLFsm(Fsm):
	def element(self, elementId, content, onenter=[], onleave=[]):
		entry = State()
		final = State()
		entry.addTransition(elementId, content.entry, onenter)
		for state in content.accepts:
			state.onleave.extend(onleave)
			state.addTransition(0, final, state.onleave)
		self.entry = entry
		self.accepts = set([final])
		return self
		
	def choice(self, fsms, onenter=[], onleave=[]):
		self.entry = State()
		self.accepts = set()
		for fsm in fsms:
			self.entry.addTransition(None, fsm.entry, list(onenter))
			self.accepts = self.accepts.union(fsm.accepts)
		self.onleave(list(onleave))
		return self

	def sequence(self, fsms, onenter=[], onleave=[]):
		fsms.reverse()
		self.entry = fsms[0].entry
		self.accepts = fsms[0].accepts
		for fsm in fsms[1:]:
			for state in fsm.accepts:
				state.addTransition(None, self.entry, list(state.onleave))
			self.entry = fsm.entry
		entry = State()
		entry.addTransition(None, self.entry, list(onenter))
		self.entry = entry
		self.onleave(list(onleave))
		return self

	def particle(term, minOccurs, maxOccurs):
		if maxOccurs == "unbounded":
			a = (copy.deepcopy(term)).kleene()
		else:
			a = type(term)().empty()
			leave = a.entry
			for i in range(0, maxOccurs - minOccurs):
				c = copy.deepcopy(term)
				c.concat(a)
				c.entry.addTransition(None, leave)
				a = c
		if minOccurs > 0:
			b = type(term)().empty()
			for i in range(0, minOccurs):
				c = copy.deepcopy(term)
				b.concat(c)
			if maxOccurs == "unbounded" or maxOccurs - minOccurs > 0:
				b.concat(a)
			return b
		return a

	def dump(self):
		states = self.reachables()
		for idx in range(0, len(states)):
			state = states[idx]
			line = ""
			line += "%s\t%s%d%s| " % ("entry:" if state == self.entry else "", "[" if state in self.accepts else " ", idx, "]" if state in self.accepts else " ")
			for label in set([t.label for t in state.transitions]):
				line += "%s -> " % label
				targets = [t.target for t in state.transitions if t.label == label]
				for target in targets:
					actions = list()
					for a in [t.actions for t in state.transitions if t.label == label and t.target == target]:
						actions.extend(a)
					line += "%d / %s | " % (states.index(target), ", ".join(["%d" % action for action in actions]))
			print line

	def determinize(self, verbose = True):
		NFAstates = self.reachables()
		if verbose: print "Determinizing NFA of size %d" % len(NFAstates)
		states, actions = XMLFsm.closure(self.entry)
		sets = [states]
		queue = deque([(0, actions)])
		DFAstates = [State()]
		DFA = XMLFsm()
		DFA.entry = DFAstates[0]
		if len([x for x in states if x in self.accepts]) > 0:
			DFA.accepts.add(DFAstates[0])
		while len(queue) > 0:
			i, actions = queue.popleft()
			transitions = dict()
			tactions = dict()
			# for every NFA state from active set
			for state in sets[i]:
				# collect non-epsilon transitions
				for trans in state.transitions:
					if trans.label is not None:
						# as key -> list of target states
						if not transitions.has_key(trans.label):
							transitions[trans.label] = set()
							tactions[trans.label] = list( actions[ sets[i].index(state) ] )
						if trans.target not in transitions[trans.label]:
							transitions[trans.label].add(trans.target)
						tactions[trans.label].extend(trans.actions)

			for label, targets in transitions.iteritems():
				targets, actions = XMLFsm.closure(targets)
				if targets not in sets:
					j = len(sets)
					queue.append((j, actions))
					sets.append(targets)
					DFAstates.append(State())
					if len([x for x in targets if x in self.accepts]) > 0:
						DFA.accepts.add(DFAstates[j])
#						onleave_actions = [list(target.onleave) for target in targets if target in self.accepts]
#						print "actions when leaving state %d: %s" % (j, onleave_actions)
#						for a in onleave_actions:
#							DFAstates[j].onleave.extend(a)
				else:
					j = sets.index(targets)
				DFAstates[i].addTransition(label, DFAstates[j], tactions[label])
		return DFA

	def minimize(self, verbose = True):
		marked = []
		unmarked = []
		states = self.reachables()
		if verbose: print "Minimizing DFA of size %d" % len(states)
		F = [states.index(x) for x in self.accepts]
		for p in range(0, len(states) - 1):
			for q in range(p + 1, len(states)):
				if (p in F) != (q in F):
					marked.append([p, q])
				else:
					unmarked.append([p, q])
		oldlength = -1

		list2dict = lambda src: dict((t.label, [s.target for s in src if s.label == t.label]) for t in src)

		while len(unmarked) != oldlength:
			oldlength = len(unmarked)
			for pq in unmarked:
				p = states[pq[0]]
				q = states[pq[1]]
				mark = False
#				if len(p.transitions) != len(q.transitions):
#					mark = True
#				else:
				if True:
					if len(p.transitions) < len(q.transitions): p, q = q, p
					ptrans = list2dict(p.transitions)
					qtrans = list2dict(q.transitions)

					for label, targets in ptrans.iteritems():
						ptarget = states.index(reduce(lambda x, y: y if x is None else x, targets))
						if qtrans.has_key(label):
							qtarget = states.index(reduce(lambda x, y: y if x is None else x, qtrans[label]))
							pacts = list(chain.from_iterable(t.actions for t in p.transitions if t.label == label and t.target == states[ptarget]))
							qacts = list(chain.from_iterable(t.actions for t in q.transitions if t.label == label and t.target == states[qtarget]))
#						print "for label %s and states (%d, %d): %s %s= %s" % (label, ptarget, qtarget, pacts, "!" if pacts != qacts else "=", qacts)
							if ([ptarget, qtarget] in marked) or ([qtarget, ptarget] in marked) or (pacts != qacts):
								mark = True
								break
						else:
							mark = True
							break
				if mark:
					marked.append(pq)
					unmarked.remove(pq)
		if verbose: print "Remaining unmarked: %s" % unmarked
		merge = []

		for pq in unmarked:
			inserted = False
			for l in merge:
				if (pq[0] in l) or (pq[1] in l):
					if pq[0] not in l: l.append(pq[0])
					if pq[1] not in l: l.append(pq[1])
					inserted = True
					break
			if not inserted:
				merge.append(pq)

#		print "Merge: %s" % merge
		state2set = dict()
		set_num = 0
		for pq in unmarked:
			pe = state2set.has_key(pq[0])
			qe = state2set.has_key(pq[1])
			if pe and not qe:
				state2set[pq[1]] = state2set[pq[0]]
			elif not pe and qe:
				state2set[pq[0]] = state2set[pq[1]]
			elif not pe and not qe:
				state2set[pq[0]] = set_num
				state2set[pq[1]] = set_num
				set_num += 1

		for i in range(0, len(states)):
			if not state2set.has_key(i):
				state2set[i] = set_num
				set_num += 1

		sets = []
		set2states = dict()
		for i in range(0, set_num):
			set2states[i] = [k for k, v in state2set.items() if v == i]
			sets.append(State())

		for set, state_list in set2states.iteritems():
			for state in state_list:
				for label, targets in list2dict(states[state].transitions).iteritems():
					if len([t for t in sets[set].transitions if t.label == label]) == 0:
						target = states.index(reduce(lambda x, y: y if x is None else x, targets))
						pacts = list(chain.from_iterable(t.actions for t in states[state].transitions if t.label == label and t.target == states[target]))
#						print "Adding transition to DFA for label %s -> %d / %s" % (label, states[target].id, pacts)
						sets[set].addTransition(label, sets[state2set[target]], pacts)
				break
		optDFA = XMLFsm()
		optDFA.entry = sets[state2set[states.index(self.entry)]]
		for state in [sets[state2set[states.index(i)]] for i in self.accepts]:
			optDFA.accepts.add(state)
		if verbose: print "DFA reduced from %d to %d states (%.1f)" % (len(states), len(sets), 100.0 * len(sets) / len(states))
		return optDFA

	def split(self, Bs, B, a):
		A = ([], [])
		for b in Bs:
			for t in b.transitions:
				if b.label == a:
					A[int(bool(b in B))].append(b)
					break
		return A

	def hopcroft(self):
		Q = self.reachables()
		dinv = [dict() for i in range(0, len(Q))]
		for i in range(0, len(Q)):
			for trans in Q[i].transitions:
				target = Q.index(trans.target)
				if trans.label not in dinv[target]:
					dinv[target][trans.label] = set()
				dinv[target][trans.label].add(i)
		print dinv
		F = self.accepts
		P = [ F, set(Q) - F ]
		W = deque(P[1])
		while len(W) > 0:
			A = W.popleft()
#		sigma = set([trans.label for trans in [transitions for transitions in [state.transitions for state in A]]])
			sigma = set()
			for transitions in [state.transitions for state in A]:
				for trans in transitions:
					sigma = sigma.add(trans.label)
			print "Sigma: %s" % sigma
			for c in sigma:
				X = set()
				for state in A:
					X.union(dinv[Q.index(state)][c])
				print "X for label %s: %s" % (c, X)
		return Q
			
if __name__ == "__main__":
	fsm = XMLFsm().element("A",
            XMLFsm().choice([
                XMLFsm().element("C", XMLFsm().empty(), [2], [4]),
                XMLFsm().element("D", XMLFsm().empty(), [3], [5])
            ], [1], [6]).particle(1, "unbounded"), [0], [7]).particle(1, "unbounded")
	fsm.dump()
	dfa = fsm.determinize()
	dfa.dump()
	dfa = dfa.minimize()
	dfa.dump()
