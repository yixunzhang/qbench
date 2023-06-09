import numpy as np
import torch.utils.data as torch_data
from .localdata import get_file_names
from .profiler import TimeEvaluator
from torch.utils.data.distributed import DistributedSampler
import torch


class TrainLoader:
    def __init__(self, batch_size, data_size, distributed):
        self.batch_size = batch_size
        self.data_size = data_size
        self.distributed = distributed

    @staticmethod
    def worker_init_fn_local(_):
        worker_info = torch.utils.data.get_worker_info()
        ds = worker_info.dataset
        lst = []
        for name in ds.local_name_all:
            lst += [np.load(name, mmap_mode="r")]
        ds.local_tuple_all = lst

    def __call__(self, data_set, num_workers, local):
        sampler = DistributedSampler(data_set) if self.distributed else DataSampler(self.data_size)
        worker_init_fn = self.worker_init_fn_pyibverbs if not local else self.worker_init_fn_local
        return torch_data.DataLoader(dataset=data_set, batch_size=self.batch_size, sampler=sampler, timeout=100000,
                                        worker_init_fn=worker_init_fn, num_workers=num_workers, pin_memory=True)

class DataSet(torch_data.dataset.Dataset):
    def __init__(self, config_name, ti_dim=2500, data_size = 5*10**6, interval=10**3, clip=100, local=False):
        self.local = local
        self.clip = clip
        self.data_size = data_size
        if self.local:
            self.local_name_all, self.local_tuple_all= get_file_names(config_name), None
        else:
            raise RuntimeError("Not Implemented")
        
        self.sample = np.random.randint(0, self.clip, ti_dim)
        self.positions = np.random.randint(10 ** 3, data_size, data_size)
        self.interval = interval
        self.pointer = 0

    def __getitem__(self, ind):
        if self.pointer % self.interval == 0:
            TimeEvaluator.get_info("get_item")
        if self.pointer >= len(self):
            raise StopIteration
        self.pointer += 1
        result = self.positions[ind]
        tuple_all = self.local_tuple_all if self.local else self.remote_tuple_all
        with TimeEvaluator.time_context("get_item_time_usage"):
            ind_x = [tuple[result-self.clip + 1: result + 1][self.sample] for tuple in tuple_all]
        return np.concatenate(ind_x, axis=-1), np.zeros(10, np.float32)

    def __len__(self):
        return self.data_size

class DataSampler(torch_data.Sampler):
    def __init__(self, data_size):
        super(DataSampler, self).__init__([])
        self.pointer = 0
        self.positions = np.random.randint(10 ** 3, data_size, data_size)
        self.data_size = data_size

    def __iter__(self):
        return self

    def __next__(self):
        if self.pointer >= len(self):
            raise StopIteration
        result = self.positions[self.pointer]
        self.pointer += 1
        return result

    def __len__(self):
        return self.data_size
