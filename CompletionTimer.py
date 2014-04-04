import time
#TODO add expected remaining functions.
class CompletionTimer(object):
    def __init__(self,initialDuration=60,units=1,eventName="",alpha=.3,reportStr="Event :{eventName}:. Estimated time taken :{lpfDuration}:. Estimated remaining :{estimate}:."):
        self.eventName = eventName
        self.start = None
        self.stop = None
        self.lastStart = None
        self.lastStop = None
        self.duration = initialDuration
        self.lastDuration = initialDuration
        self.lpfDuration = initialDuration
        self.alpha = alpha
        self.reportStr = reportStr
        self.durationFmt = "Event :%s: Estimated time taken :%0.1f: minutes."
        self.estimateFmt = "Event :%s: Estimated time to completion :%0.1f: minutes."
        self.units = units
        self.estimate = self.units*self.lpfDuration/60

    def startEvent(self):
        self.lastStart = self.start
        self.start = time.time()
        
    def stopEvent(self):
        self.lastStop = self.stop
        self.lastDuration = self.duration
        self.stop = time.time()
        self.duration = self.stop - self.start
        self.lpfDuration = self.lastDuration*(1-self.alpha) + self.duration*self.alpha
        self.units = self.units-1
        self.estimate = self.units*self.lpfDuration/60.0
        
    def __str__(self):
        vals = dict(self.__dict__)
        vals['duration'] = vals['duration']/60
        vals['lpfDuration'] = vals['lpfDuration']/60
        return self.reportStr.format(**vals)
    def durationStr(self):
        return self.durationFmt%(self.eventName,self.duration/60.0)
    def lpfDurationStr(self):
        return self.durationFmt%(self.eventName,self.lpfDuration/60.0)
    def estimateStr(self):
        return self.estimateFmt%(self.eventName,self.units*self.lpfDuration/60.0)
    
def main():
    print("Testing Initialization with default arguments.")
    ct = CompletionTimer(units=100)
    print("Testing start time. Wait .5 minute.")
    ct.startEvent()
    time.sleep(30)
    print("Testing stop time.")
    ct.stopEvent()
    print("Testing __str__. Expected .8 minute.")
    print(ct)
    print("Testing durationStr. Expected .5 minute.")
    print(ct.durationStr())
    print("Testing lpfDurationStr. Expected .8 minutes.")
    print(ct.lpfDurationStr())
    print("Testing estimateStr. Expected .8 and 79.2 minutes.")
    print(ct.estimateStr())
    
    print("Testing start time. Wait 1 minute.")
    ct.startEvent()
    time.sleep(60)
    ct.stopEvent()
    print("Testing __str__. Expected .7 minutes.")
    print(ct)
    # print("Testing durationStr. Expected 1 minutes.")
    # print(ct.durationStr())
    # print("Testing lpfDurationStr. Expected .7 minutes.")
    # print(ct.lpfDurationStr())
    print("Testing estimateStr. Expected 68.6 minutes.")
    print(ct.estimateStr())
    
if __name__ == "__main__":
    main()