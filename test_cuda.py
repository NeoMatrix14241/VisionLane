import torch

def verify_cuda():
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU Device: {torch.cuda.get_device_name(0)}")
        # Test CUDA
        x = torch.rand(5,3).cuda()
        print(f"Test tensor device: {x.device}")

if __name__ == "__main__":
    verify_cuda()