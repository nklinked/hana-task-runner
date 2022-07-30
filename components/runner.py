import asyncio
import logging
import time

class Runner:
    def __init__(self, sem_value):
        self.sem_value = sem_value

    async def execute_task(self, semaphore, partial):
        loop = asyncio.get_running_loop()
        async with semaphore:
            await loop.run_in_executor(None, partial)

    async def execute_worklist(self, loop, partials):
        semaphore = asyncio.Semaphore(value=self.sem_value)
        worklist = []
        for partial in partials:
            worklist.append(self.execute_task(semaphore, partial))
        logging.info(f'Limited to {self.sem_value} parallel tasks')
        await asyncio.wait(worklist)

    def run(self, partials):
        start = time.time()
        loop = asyncio.get_event_loop()
        logging.info('Started parallel processing')
        loop.run_until_complete(self.execute_worklist(loop, partials))
        loop.close()
        end = time.time()
        logging.info(f'Finished parallel processing in {end-start}s')
