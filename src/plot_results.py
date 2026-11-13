import matplotlib.pyplot as plt
import numpy as np

def plot_all_metrics(results):
    results = np.array(results)

    med_bpp = results[:, 0]
    cnn_bpp = results[:, 1]

    med_mae = results[:, 2]
    cnn_mae = results[:, 3]

    med_psnr = results[:, 4]
    cnn_psnr = results[:, 5]

    med_ssim = results[:, 6]
    cnn_ssim = results[:, 7]

    x = np.arange(len(med_bpp))

    # -------- Capacity --------
    plt.figure()
    plt.plot(x, med_bpp, label="MED")
    plt.plot(x, cnn_bpp, label="CNN")
    plt.title("Capacity (bpp)")
    plt.xlabel("Image Index")
    plt.ylabel("bpp")
    plt.legend()
    plt.grid()
    plt.savefig("capacity.png")

    # -------- MAE --------
    plt.figure()
    plt.plot(x, med_mae, label="MED")
    plt.plot(x, cnn_mae, label="CNN")
    plt.title("MAE Comparison")
    plt.xlabel("Image Index")
    plt.ylabel("MAE")
    plt.legend()
    plt.grid()
    plt.savefig("mae.png")

    # -------- PSNR --------
    plt.figure()
    plt.plot(x, med_psnr, label="MED")
    plt.plot(x, cnn_psnr, label="CNN")
    plt.title("PSNR Comparison")
    plt.xlabel("Image Index")
    plt.ylabel("PSNR (dB)")
    plt.legend()
    plt.grid()
    plt.savefig("psnr.png")

    # -------- SSIM --------
    plt.figure()
    plt.plot(x, med_ssim, label="MED")
    plt.plot(x, cnn_ssim, label="CNN")
    plt.title("SSIM Comparison")
    plt.xlabel("Image Index")
    plt.ylabel("SSIM")
    plt.legend()
    plt.grid()
    plt.savefig("ssim.png")

    plt.show()