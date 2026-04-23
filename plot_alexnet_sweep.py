import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_sweep():
    csv_file = 'alexnet_sweep_summary.csv'
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return

    df = pd.read_csv(csv_file)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df['table_size'], df['cpu_total'], marker='o', linestyle='-', color='b', label='CPU Total (User+Sys)')
    plt.plot(df['table_size'], df['real_time'], marker='s', linestyle='--', color='g', label='Real Time (Wall-clock)')
    
    plt.title('AlexNet Table Size vs. Execution Time')
    plt.xlabel('Q-Table Size')
    plt.ylabel('Time (Seconds)')
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend()
    
    # Annotate points
    for i, txt in enumerate(df['cpu_total']):
        plt.annotate(f"{txt:.1f}s", (df['table_size'][i], df['cpu_total'][i]), textcoords="offset points", xytext=(0,10), ha='center')

    output_plot = 'alexnet_sweep_plot.png'
    plt.savefig(output_plot)
    print(f"Plot saved to {output_plot}")

if __name__ == "__main__":
    plot_sweep()
