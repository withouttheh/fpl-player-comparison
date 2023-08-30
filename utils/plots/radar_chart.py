import numpy as np
import matplotlib.pyplot as plt

class RadarChartPlotter:
	def __init__(self):
		plt.style.use('ggplot')

	def plot_basic_chart(self, values, labels):
		angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False)
		angles = np.concatenate((angles, [angles[0]]))
		labels.append(labels[0])
		values.append(values[0])

		fig = plt.figure(figsize=(8, 8))
		ax = fig.add_subplot(polar=True)
		ax.plot(angles, values)
		return fig

	def plot_customized_chart(self, values, labels):
		angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False)
		angles = np.concatenate((angles, [angles[0]]))
		labels.append(labels[0])
		values.append(values[0])

		fig = plt.figure(figsize=(6, 6))
		ax = fig.add_subplot(polar=True)
		ax.plot(angles, values, 'o--', color='g', label='Data')
		ax.fill(angles, values, alpha=0.25, color='g')
		ax.set_thetagrids(angles * 180/np.pi, labels)
		plt.grid(True)
		plt.tight_layout()
		plt.legend()
		return fig